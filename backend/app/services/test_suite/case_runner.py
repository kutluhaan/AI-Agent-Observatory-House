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
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_suite import TestCase, TestCaseResult, TestRun
from app.services.agent.base import AgentConfig, AgentError
from app.services.providers.factory import get_provider
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
        provider = await get_provider(db, run.organization_id, agent_row.provider)
    except Exception as exc:
        return await _save_result(
            db, run.id, case.id,
            status="error",
            error_message=f"Provider yüklenemedi: {exc}",
        )

    config = AgentConfig(
        agent_id=agent_row.id,
        org_id=run.organization_id,
        name=agent_row.name,
        system_prompt=agent_row.system_prompt,
        provider=agent_row.provider,
        model=agent_row.model,
        temperature=agent_row.temperature,
        max_tokens=agent_row.max_tokens,
        max_steps=agent_row.max_steps,
        timeout_seconds=agent_row.timeout_seconds,
        tool_names=agent_row.tool_names or [],
        hitl_tool_names=[],  # Test sırasında HITL devre dışı
    )

    sandbox = AgentSandbox(config=config, provider=provider, redis=redis, db=db)

    # Çalıştır
    try:
        sandbox_result: SandboxResult = await sandbox.run(case.input)
    except AgentError as exc:
        return await _save_result(
            db, run.id, case.id,
            status="error",
            error_message=f"{exc.code}: {exc.message}",
        )
    except Exception as exc:
        logger.error("test_case_runner.unexpected_error", case_id=str(case.id), error=str(exc))
        return await _save_result(
            db, run.id, case.id,
            status="error",
            error_message=str(exc),
        )

    # Assertion'ları değerlendir
    assertion_results = evaluate_all(
        [{"type": a["type"], "value": a["value"]} for a in (case.assertions or [])],
        sandbox_result,
    )
    all_passed = all(r.passed for r in assertion_results)

    # RAG metrikleri
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
    total_tokens = sum(sandbox_result.agent_result.total_usage.values()) if ar.total_usage else None

    return await _save_result(
        db, run.id, case.id,
        status="passed" if all_passed else "failed",
        output=ar.content,
        trace_id=ar.trace_id,
        latency_ms=sandbox_result.latency_ms,
        steps_taken=ar.steps_taken,
        total_tokens=total_tokens,
        assertions_results=[r.to_dict() for r in assertion_results],
        rag_metrics=rag_metrics,
        trajectory=sandbox_result.trajectory,
        cost_usd=sandbox_result.cost_usd,
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
        cost_usd=cost_usd,
        error_message=error_message,
        created_at=datetime.now(UTC),
    )
    db.add(result)
    await db.flush()  # ID ata — commit ExperimentRunner tarafından yapılır
    return result
