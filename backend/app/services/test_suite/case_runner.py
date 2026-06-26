"""
TestCaseRunner — M11

Tek bir TestCase'i çalıştırır:
  1. Agent'ı DB'den yükler
  2. Provider'ı hazırlar
  3. AgentSandbox üzerinden çalıştırır
  4. Assertion'ları değerlendirir
  5. RAG metriklerini hesaplar (rag_context varsa)
  6. TestCaseResult'u DB'ye yazar
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_suite import TestCase, TestCaseResult, TestRun
from app.services.agent.base import AgentConfig, AgentError
from app.services.providers.factory import get_provider_for_agent
from app.services.test_suite.assertions import SandboxResult, evaluate_all
from app.services.test_suite.rag_evaluator import evaluate_rag
from app.services.test_suite.sandbox import AgentSandbox

logger = structlog.get_logger()


async def run_case(
    case: TestCase,
    run: TestRun,
    db: AsyncSession,
    redis: Any,
    *,
    override_agent_id: uuid.UUID | None = None,
) -> TestCaseResult:
    """
    Tek bir test case'i çalıştırır ve TestCaseResult döner (DB'ye kaydedilmiş).

    Args:
        case: DB'den yüklenmiş TestCase.
        run: Bu case'in ait olduğu TestRun.
        db: Async DB session.
        redis: Redis bağlantısı (Tracer + sandbox için).
        override_agent_id: Suite-level veya case-level agent'ı geçersiz kıl.
    """
    from sqlalchemy import select
    from app.models.agent import Agent

    agent_id = override_agent_id or case.agent_id
    if agent_id is None:
        return await _save_result(
            db, run.id, case.id,
            status="error",
            error_message="agent_id belirtilmedi — case veya suite seviyesinde zorunlu.",
        )

    # Agent yükle
    agent_row = (await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == run.organization_id,
            Agent.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()

    if agent_row is None:
        return await _save_result(
            db, run.id, case.id,
            status="error",
            error_message=f"Agent '{agent_id}' bulunamadı veya pasif.",
        )

    # Provider yükle
    try:
        provider = await get_provider_for_agent(db, agent_row)
    except Exception as exc:
        return await _save_result(
            db, run.id, case.id,
            status="error",
            error_message=f"Provider yüklenemedi: {exc}",
        )

    # F4.3: A/B — run'a system_prompt_override varsa agent'ınkini geçici ezer (kalıcı değil)
    system_prompt = getattr(run, "system_prompt_override", None) or agent_row.system_prompt

    # Skill'leri dahil et — normal chat ile aynı davranış
    from app.services.agent import knowledge_store
    from app.services.agent.tools.skills import SKILL_TOOL_NAMES
    tool_names = list(agent_row.tool_names or [])
    always_on = await knowledge_store.load_always_on(db, agent_row.id)
    if always_on:
        system_prompt = f"{system_prompt}\n\n{always_on}"
    if await knowledge_store.has_skills(db, agent_row.id):
        tool_names += SKILL_TOOL_NAMES
        system_prompt += (
            "\n\nYou have skills available. Call list_skills to discover them and "
            "read_skill to read one before a task it covers."
        )

    config = AgentConfig(
        agent_id=agent_row.id,
        org_id=run.organization_id,
        name=agent_row.name,
        system_prompt=system_prompt,
        provider=agent_row.provider,
        model=agent_row.model,
        temperature=agent_row.temperature,
        max_tokens=agent_row.max_tokens,
        max_steps=agent_row.max_steps,
        timeout_seconds=agent_row.timeout_seconds,
        tool_names=tool_names,
        hitl_tool_names=[],  # Test sırasında HITL devre dışı
    )

    # F7.2: agent'ın MCP tool'larını çözümle
    from app.services.mcp.resolver import resolve_agent_mcp_tools
    mcp_tools = await resolve_agent_mcp_tools(db, agent_row)
    # B1: custom HTTP tool'ları
    from app.services.agent.custom_tools import resolve_agent_custom_tools
    http_tools = await resolve_agent_custom_tools(db, agent_row)

    sandbox = AgentSandbox(config=config, provider=provider, redis=redis, db=db, mcp_tools=mcp_tools, http_tools=http_tools)

    # F6: senaryo modu — case'in steps'i varsa çok-turlu çalıştır (checkpoint'ler)
    if getattr(case, "steps", None):
        return await _run_scenario(db, run, case, sandbox)

    # Faz C: tutarlılık — case'i repeat kez çalıştır
    repeat = max(1, int(getattr(case, "repeat", 1) or 1))
    min_pass_rate = float(getattr(case, "min_pass_rate", 1.0) or 1.0)

    outcomes: list[_RunOutcome | None] = []
    for _ in range(repeat):
        try:
            outcomes.append(await _evaluate_once(sandbox, case, provider, agent_row.model))
        except AgentError as exc:
            if repeat == 1:
                return await _save_result(
                    db, run.id, case.id, status="error",
                    error_message=f"{exc.code}: {exc.message}",
                )
            outcomes.append(None)
        except Exception as exc:
            logger.error("test_case_runner.unexpected_error", case_id=str(case.id), error=str(exc))
            if repeat == 1:
                return await _save_result(db, run.id, case.id, status="error", error_message=str(exc))
            outcomes.append(None)

    valid = [o for o in outcomes if o is not None]
    if not valid:
        return await _save_result(
            db, run.id, case.id, status="error",
            error_message="Tüm tekrarlar hata verdi.",
        )

    rep = valid[0]  # temsilci: ilk başarılı çalıştırma

    if repeat == 1:
        consistency = None
        status = "passed" if rep.passed else "failed"
        total_tokens = rep.total_tokens
        cost_usd = rep.cost_usd
        latency_ms = rep.latency_ms
    else:
        passed_runs = sum(1 for o in valid if o.passed)
        errored = sum(1 for o in outcomes if o is None)
        pass_rate = passed_runs / repeat  # hatalı tekrarlar geçmemiş sayılır
        status = "passed" if pass_rate >= min_pass_rate else "failed"
        total_tokens = sum(o.total_tokens or 0 for o in valid) or None
        cost_total = sum(o.cost_usd or 0 for o in valid)
        cost_usd = round(cost_total, 6) if cost_total else None
        latency_ms = round(sum(o.latency_ms for o in valid) / len(valid))
        consistency = {
            "runs": repeat,
            "passed_runs": passed_runs,
            "errored_runs": errored,
            "pass_rate": round(pass_rate, 4),
            "min_pass_rate": min_pass_rate,
            "runs_detail": [
                ({"passed": o.passed, "latency_ms": o.latency_ms,
                  "total_tokens": o.total_tokens, "cost_usd": o.cost_usd}
                 if o is not None else {"passed": False, "errored": True})
                for o in outcomes
            ],
        }

    return await _save_result(
        db, run.id, case.id,
        status=status,
        output=rep.output,
        trace_id=rep.trace_id,
        latency_ms=latency_ms,
        steps_taken=rep.steps_taken,
        total_tokens=total_tokens,
        assertions_results=rep.assertion_results,
        rag_metrics=rep.rag_metrics,
        trajectory=rep.trajectory,
        judge_results=rep.judge_results,
        cost_usd=cost_usd,
        consistency=consistency,
    )


async def _run_scenario(db, run, case, sandbox) -> TestCaseResult:
    """F6: Çok-turlu senaryo. Her adım biriken konuşma geçmişiyle çalışır; o adımın
    checkpoint'leri (assertions) değerlendirilir. Davranış: 'devam et, hepsini raporla'
    — bir adım kalsa da sonraki adımlar çalışır. Case status: TÜM adımlar geçerse passed."""
    history: list[dict[str, str]] = []
    steps_results: list[dict] = []
    all_passed = True
    total_latency = 0
    total_tokens = 0
    total_cost = 0.0
    rep_trace: str | None = None
    last_trajectory = None

    for idx, step in enumerate(case.steps or []):
        s_input = step.get("input", "")
        s_assertions = step.get("assertions", []) or []
        try:
            sandbox_result: SandboxResult = await sandbox.run(s_input, history=history)
        except Exception as exc:
            logger.error("test_case_runner.scenario_step_error", step=idx, error=str(exc))
            all_passed = False
            steps_results.append({
                "step": idx, "input": s_input, "output": None, "passed": False,
                "error": str(exc), "assertions_results": [],
            })
            history.append({"role": "user", "content": s_input})
            history.append({"role": "assistant", "content": ""})
            continue

        ar = sandbox_result.agent_result
        a_results = evaluate_all(
            [{"type": a["type"], "value": a["value"]} for a in s_assertions],
            sandbox_result,
        )
        step_passed = all(r.passed for r in a_results)
        all_passed = all_passed and step_passed

        total_latency += sandbox_result.latency_ms
        if ar.total_usage:
            total_tokens += sum(ar.total_usage.values())
        if sandbox_result.cost_usd:
            total_cost += sandbox_result.cost_usd
        rep_trace = rep_trace or ar.trace_id
        last_trajectory = sandbox_result.trajectory

        steps_results.append({
            "step": idx,
            "input": s_input,
            "output": ar.content,
            "passed": step_passed,
            "latency_ms": sandbox_result.latency_ms,
            "assertions_results": [r.to_dict() for r in a_results],
        })
        history.append({"role": "user", "content": s_input})
        history.append({"role": "assistant", "content": ar.content})

    rep_output = steps_results[-1]["output"] if steps_results else None
    flat_assertions = [a for s in steps_results for a in s.get("assertions_results", [])]

    return await _save_result(
        db, run.id, case.id,
        status="passed" if all_passed else "failed",
        output=rep_output,
        trace_id=rep_trace,
        latency_ms=round(total_latency) if total_latency else None,
        total_tokens=total_tokens or None,
        assertions_results=flat_assertions,
        trajectory=last_trajectory,
        steps_results=steps_results,
        cost_usd=round(total_cost, 6) if total_cost else None,
    )


@dataclass
class _RunOutcome:
    passed: bool
    output: str
    trace_id: str
    latency_ms: int
    steps_taken: int
    total_tokens: int | None
    cost_usd: float | None
    assertion_results: list   # [dict]
    judge_results: list | None
    rag_metrics: dict | None
    trajectory: list


async def _evaluate_once(sandbox, case, provider, model) -> _RunOutcome:
    """Agent'ı bir kez çalıştırır, assertion + judge + RAG değerlendirir.
    Sandbox hatasında exception fırlatır (çağıran tarafından yakalanır)."""
    sandbox_result: SandboxResult = await sandbox.run(case.input)

    assertion_results = evaluate_all(
        [{"type": a["type"], "value": a["value"]} for a in (case.assertions or [])],
        sandbox_result,
    )
    assertions_passed = all(r.passed for r in assertion_results)

    judge_results = None
    judges_passed = True
    if case.judges:
        from app.services.test_suite.judge import evaluate_judges
        judge_results = await evaluate_judges(
            case.judges, case.input, sandbox_result.agent_result.content,
            sandbox_result, provider, model,
        )
        judges_passed = all(j["passed"] for j in judge_results if j.get("passed") is not None)

    rag_metrics = None
    if case.rag_context:
        try:
            rag_metrics = await evaluate_rag(
                question=case.input,
                answer=sandbox_result.agent_result.content,
                contexts=case.rag_context,
            )
        except Exception as exc:
            logger.warning("test_case_runner.rag_eval_failed", error=str(exc))

    ar = sandbox_result.agent_result
    total_tokens = sum(ar.total_usage.values()) if ar.total_usage else None

    return _RunOutcome(
        passed=assertions_passed and judges_passed,
        output=ar.content,
        trace_id=ar.trace_id,
        latency_ms=sandbox_result.latency_ms,
        steps_taken=ar.steps_taken,
        total_tokens=total_tokens,
        cost_usd=sandbox_result.cost_usd,
        assertion_results=[r.to_dict() for r in assertion_results],
        judge_results=judge_results,
        rag_metrics=rag_metrics,
        trajectory=sandbox_result.trajectory,
    )


async def _save_result(
    db: AsyncSession,
    run_id: uuid.UUID,
    case_id: uuid.UUID,
    *,
    status: str,
    output: str | None = None,
    trace_id: str | None = None,
    latency_ms: int | None = None,
    steps_taken: int | None = None,
    total_tokens: int | None = None,
    assertions_results: list | None = None,
    rag_metrics: dict | None = None,
    trajectory: list | None = None,
    judge_results: list | None = None,
    consistency: dict | None = None,
    steps_results: list | None = None,
    cost_usd: float | None = None,
    error_message: str | None = None,
) -> TestCaseResult:
    result = TestCaseResult(
        id=uuid.uuid4(),
        run_id=run_id,
        case_id=case_id,
        status=status,
        output=output,
        trace_id=trace_id,
        latency_ms=latency_ms,
        steps_taken=steps_taken,
        total_tokens=total_tokens,
        assertions_results=assertions_results or [],
        rag_metrics=rag_metrics,
        trajectory=trajectory,
        judge_results=judge_results,
        consistency=consistency,
        steps_results=steps_results,
        cost_usd=cost_usd,
        error_message=error_message,
        created_at=datetime.now(UTC),
    )
    db.add(result)
    await db.flush()  # ID ata — commit ExperimentRunner tarafından yapılır
    return result
