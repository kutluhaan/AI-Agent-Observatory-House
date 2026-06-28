"""
Workflow Runner — Faz 2

BFS graph traversal + fire-and-forget execution.
Her node için WorkflowNodeResult oluşturulur, WS üzerinden broadcast edilir.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis_pool
from app.models.workflow import Workflow, WorkflowNodeResult, WorkflowRun
from app.ws.traces import manager as ws_manager

logger = structlog.get_logger()


# ── Entry point ───────────────────────────────────────────────

def start_workflow_run(workflow_id: uuid.UUID, run_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Schedule background execution (fire-and-forget)."""
    asyncio.create_task(_execute_workflow(workflow_id, run_id, org_id))


# ── Core BFS executor ─────────────────────────────────────────

async def _execute_workflow(
    workflow_id: uuid.UUID,
    run_id: uuid.UUID,
    org_id: uuid.UUID,
) -> None:
    async with AsyncSessionLocal() as db:
        try:
            wf = (await db.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )).scalar_one_or_none()
            run = (await db.execute(
                select(WorkflowRun).where(WorkflowRun.id == run_id)
            )).scalar_one_or_none()

            if wf is None or run is None:
                return

            graph = wf.graph_json or {}
            raw_nodes: list[dict] = graph.get("nodes", [])
            edges: list[dict] = graph.get("edges", [])
            node_map = {n["id"]: n for n in raw_nodes}

            # Find start node
            start_nodes = [n for n in raw_nodes if n.get("type") == "start"]
            if not start_nodes:
                await _fail_run(db, run, org_id, "Start node bulunamadı.")
                return

            context: dict[str, dict] = {}
            queue: deque[str] = deque([start_nodes[0]["id"]])
            visited: set[str] = set()

            while queue:
                node_id = queue.popleft()
                if node_id in visited:
                    continue
                visited.add(node_id)

                node = node_map.get(node_id)
                if node is None:
                    continue

                # Mark node running
                nr = await _upsert_node_result(db, run_id, node_id, "running")
                await _broadcast(org_id, run_id, node_id, "running", None, None)

                try:
                    output, active_handle = await _execute_node(node, context, org_id, db)
                    context[node_id] = {"output": output}
                    await _finish_node_result(db, nr, "completed", output, None)
                    await _broadcast(org_id, run_id, node_id, "completed", output, None)
                except Exception as exc:
                    err = str(exc)
                    logger.error("workflow_runner.node_failed", run_id=str(run_id), node_id=node_id, error=err)
                    await _finish_node_result(db, nr, "failed", None, err)
                    await _broadcast(org_id, run_id, node_id, "failed", None, err)
                    await _fail_run(db, run, org_id, f"Node '{node_id}' başarısız: {err}")
                    return

                # Follow outgoing edges
                for edge in edges:
                    if edge.get("source") != node_id:
                        continue
                    # Decision: only follow the active handle
                    if node.get("type") == "decision" and active_handle:
                        if edge.get("sourceHandle") != active_handle:
                            continue
                    target = edge.get("target")
                    if target and target not in visited:
                        queue.append(target)

            # All nodes done
            run.status = "completed"
            run.ended_at = datetime.now(UTC)
            await db.commit()
            await _broadcast_run(org_id, run_id, "completed")

        except Exception as exc:
            logger.error("workflow_runner.unexpected", run_id=str(run_id), error=str(exc))
            # Reopen session to mark run failed
            async with AsyncSessionLocal() as db2:
                run2 = (await db2.execute(
                    select(WorkflowRun).where(WorkflowRun.id == run_id)
                )).scalar_one_or_none()
                if run2:
                    run2.status = "failed"
                    run2.error = str(exc)
                    run2.ended_at = datetime.now(UTC)
                    await db2.commit()
            await _broadcast_run(org_id, run_id, "failed")


# ── Node executor ─────────────────────────────────────────────

async def _execute_node(
    node: dict,
    context: dict[str, dict],
    org_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[str, str | None]:
    """Returns (output_text, active_handle_or_None)."""
    node_type: str = node.get("type", "")
    data: dict = node.get("data") or {}

    if node_type == "start":
        return "Workflow başladı.", None

    if node_type == "end":
        return "Workflow tamamlandı.", None

    if node_type == "agent":
        agent_id_str = data.get("agent_id")
        if not agent_id_str:
            raise ValueError("agent_id belirtilmedi.")
        note = data.get("note", "")
        prev = _prev_output(context)
        user_input = "\n\n".join(filter(None, [note, prev])) or "Görevi gerçekleştir."
        output = await _run_agent(uuid.UUID(agent_id_str), org_id, user_input, db)
        return output, None

    if node_type == "note":
        note = data.get("note", "")
        if not note:
            return "(boş not)", None
        prev = _prev_output(context)
        # Orkestratör: notu + önceki çıktıyı LLM'e gönder
        output = await _orchestrate_note(note, prev, org_id, db)
        return output, None

    if node_type == "decision":
        conditions: list[dict] = data.get("conditions") or [{"handle": "evet", "label": "Evet"}]
        prev = _prev_output(context).lower()
        # Rule-based: ilk eşleşen koşul
        for cond in conditions:
            label = (cond.get("label") or "").lower()
            handle = cond.get("handle", "")
            cond_expr = (cond.get("condition") or "").lower()
            check = cond_expr or label
            if check and check in prev:
                return handle, handle
        # Fallback: LLM karar
        handle = await _orchestrate_decision(conditions, prev, data.get("note", ""), org_id, db)
        return handle, handle

    if node_type in ("team", "integration", "loop"):
        return f"[{node_type}] henüz implement edilmedi.", None

    return f"[{node_type}] bilinmeyen tip.", None


def _prev_output(context: dict[str, dict]) -> str:
    if not context:
        return ""
    return context[list(context.keys())[-1]].get("output", "")


# ── Agent executor ────────────────────────────────────────────

async def _run_agent(agent_id: uuid.UUID, org_id: uuid.UUID, user_input: str, db: AsyncSession) -> str:
    from app.models.agent import Agent
    from app.services.agent.base import AgentConfig
    from app.services.providers.factory import get_provider_for_agent
    from app.services.test_suite.sandbox import AgentSandbox

    agent_row = (await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == org_id,
            Agent.is_active == True,  # noqa: E712
        )
    )).scalar_one_or_none()

    if agent_row is None:
        raise ValueError(f"Agent {agent_id} bulunamadı veya pasif.")

    provider = await get_provider_for_agent(db, agent_row)

    system_prompt = agent_row.system_prompt
    tool_names = list(agent_row.tool_names or [])

    from app.services.agent import knowledge_store
    from app.services.agent.tools.skills import SKILL_TOOL_NAMES
    always_on = await knowledge_store.load_always_on(db, agent_row.id)
    if always_on:
        system_prompt = f"{system_prompt}\n\n{always_on}"
    if await knowledge_store.has_skills(db, agent_row.id):
        tool_names += SKILL_TOOL_NAMES

    config = AgentConfig(
        agent_id=agent_row.id,
        org_id=org_id,
        name=agent_row.name,
        system_prompt=system_prompt,
        provider=agent_row.provider,
        model=agent_row.model,
        temperature=agent_row.temperature,
        max_tokens=agent_row.max_tokens,
        max_steps=agent_row.max_steps,
        timeout_seconds=agent_row.timeout_seconds,
        tool_names=tool_names,
        hitl_tool_names=[],
    )

    from app.services.mcp.resolver import resolve_agent_mcp_tools
    from app.services.agent.custom_tools import resolve_agent_custom_tools
    mcp_tools = await resolve_agent_mcp_tools(db, agent_row)
    http_tools = await resolve_agent_custom_tools(db, agent_row)

    redis = await get_redis_pool()
    sandbox = AgentSandbox(config=config, provider=provider, redis=redis, db=db, mcp_tools=mcp_tools, http_tools=http_tools)
    result = await sandbox.run(user_input)
    return result.agent_result.content


# ── Orchestrator LLM calls ────────────────────────────────────

async def _orchestrate_note(note: str, prev_output: str, org_id: uuid.UUID, db: AsyncSession) -> str:
    """Calls LLM to execute a pure-note node."""
    provider = await _get_org_provider(org_id, db)
    if provider is None:
        return f"(Orkestratör LLM yok) Not: {note}"

    messages = [
        {"role": "user", "content": (
            f"Workflow adımı: {note}\n\n"
            f"Önceki adımın çıktısı:\n{prev_output or '(yok)'}\n\n"
            "Bu adımı gerçekleştir ve çıktını yaz."
        )}
    ]
    try:
        result = await provider.chat(messages)
        return result.content if hasattr(result, "content") else str(result)
    except Exception as exc:
        return f"(Orkestratör hata) {exc}"


async def _orchestrate_decision(
    conditions: list[dict],
    prev_output: str,
    note: str,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> str:
    """Calls LLM to pick the right decision handle."""
    provider = await _get_org_provider(org_id, db)
    handles = [c.get("handle", "") for c in conditions]
    if provider is None or not handles:
        return handles[0] if handles else "evet"

    options = ", ".join(f'"{h}"' for h in handles)
    messages = [
        {"role": "user", "content": (
            f"Karar nodu.\n{note or ''}\n\n"
            f"Önceki adımın çıktısı:\n{prev_output or '(yok)'}\n\n"
            f"Hangi yolu seçmeliyim? Seçenekler: {options}\n"
            f"Sadece seçeneği yaz, başka bir şey ekleme."
        )}
    ]
    try:
        result = await provider.chat(messages)
        text = (result.content if hasattr(result, "content") else str(result)).strip().strip('"')
        # Match to known handle
        for h in handles:
            if h.lower() in text.lower():
                return h
        return handles[0]
    except Exception:
        return handles[0]


async def _get_org_provider(org_id: uuid.UUID, db: AsyncSession):
    """Picks any available provider for the org to use as orchestrator LLM."""
    from app.models.provider import ProviderCredential
    from app.services.providers.factory import get_provider

    cred = (await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.organization_id == org_id,
        ).limit(1)
    )).scalar_one_or_none()

    if cred is None:
        return None
    try:
        return await get_provider(db, org_id, cred.provider)
    except Exception:
        return None


# ── DB helpers ────────────────────────────────────────────────

async def _upsert_node_result(
    db: AsyncSession, run_id: uuid.UUID, node_id: str, status: str
) -> WorkflowNodeResult:
    nr = WorkflowNodeResult(
        id=uuid.uuid4(),
        run_id=run_id,
        node_id=node_id,
        status=status,
        started_at=datetime.now(UTC),
    )
    db.add(nr)
    await db.commit()
    return nr


async def _finish_node_result(
    db: AsyncSession, nr: WorkflowNodeResult, status: str, output: str | None, error: str | None
) -> None:
    nr.status = status
    nr.output = output
    nr.error = error
    nr.ended_at = datetime.now(UTC)
    await db.commit()


async def _fail_run(db: AsyncSession, run: WorkflowRun, org_id: uuid.UUID, error: str) -> None:
    run.status = "failed"
    run.error = error
    run.ended_at = datetime.now(UTC)
    await db.commit()
    await _broadcast_run(org_id, run.id, "failed")


# ── WS broadcast ─────────────────────────────────────────────

async def _broadcast(
    org_id: uuid.UUID, run_id: uuid.UUID, node_id: str, status: str,
    output: str | None, error: str | None,
) -> None:
    try:
        await ws_manager.broadcast(str(org_id), {
            "type": "workflow_node_update",
            "run_id": str(run_id),
            "node_id": node_id,
            "status": status,
            "output": output,
            "error": error,
        })
    except Exception:
        pass


async def _broadcast_run(org_id: uuid.UUID, run_id: uuid.UUID, status: str) -> None:
    try:
        await ws_manager.broadcast(str(org_id), {
            "type": "workflow_run_update",
            "run_id": str(run_id),
            "status": status,
        })
    except Exception:
        pass
