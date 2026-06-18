"""
Agents Router — M9

  POST   /agents                  — agent oluştur (admin)
  GET    /agents                  — listele (member)
  GET    /agents/{id}             — detay (member)
  PATCH  /agents/{id}             — güncelle (admin)
  DELETE /agents/{id}             — sil (admin)
  GET    /agents/tools            — kayıtlı tool'ları listele (member)
  POST   /agents/{id}/run         — çalıştır; stream=true → SSE, false → JSON (member)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.responses import AppError, NotFoundError, success
from app.models.agent import Agent
from app.schemas.agents import (
    AgentResponse,
    CreateAgentRequest,
    RunAgentRequest,
    RunAgentSyncResponse,
    UpdateAgentRequest,
)
from app.services.agent.base import (
    AgentConfig,
    AgentError,
    AgentMaxStepsError,
    AgentStreamEvent,
    AgentTimeoutError,
)
from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.runner import AgentRunner
from app.services.providers.base import ProviderError
from app.services.providers.factory import get_provider
from app.services.trace_collector import Tracer

logger = structlog.get_logger()
router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────

async def _get_agent_or_404(
    agent_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> Agent:
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundError("AGENT_NOT_FOUND", "Agent not found.")
    return agent


async def _build_runner(
    agent: Agent,
    ctx: TenantContext,
    db: AsyncSession,
    redis: aioredis.Redis,
    parent_trace_id: str | None = None,
) -> AgentRunner:
    config = AgentConfig(
        agent_id=agent.id,
        org_id=ctx.org_id,  # type: ignore[arg-type]
        name=agent.name,
        system_prompt=agent.system_prompt,
        provider=agent.provider,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        max_steps=agent.max_steps,
        timeout_seconds=agent.timeout_seconds,
        tool_names=agent.tool_names or [],
    )

    # Kayıtsız tool varsa erken hata ver
    for name in config.tool_names:
        try:
            ToolRegistry.get(name)
        except KeyError:
            raise AppError(
                "TOOL_NOT_REGISTERED",
                f"Tool '{name}' is not registered. Check agent configuration.",
                422,
            )

    try:
        provider = await get_provider(db, ctx.org_id, config.provider)  # type: ignore[arg-type]
    except AppError:
        raise

    tracer = Tracer(
        redis=redis,
        organization_id=str(ctx.org_id),
        name=agent.name,
        parent_trace_id=parent_trace_id,
    )

    tool_context = ToolContext(
        org_id=ctx.org_id,  # type: ignore[arg-type]
        trace_id=tracer.trace_id,
        db=db,
        redis=redis,
    )

    return AgentRunner(config=config, provider=provider, tracer=tracer, tool_context=tool_context)


# ─── CRUD ─────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_agent(
    body: CreateAgentRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    # İsim çakışması kontrolü
    existing = await db.execute(
        select(Agent).where(
            Agent.organization_id == ctx.org_id,
            Agent.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise AppError("AGENT_NAME_CONFLICT", f"An agent named '{body.name}' already exists.", 409)

    # Kayıtsız tool varsa erken hata
    for name in body.tool_names:
        try:
            ToolRegistry.get(name)
        except KeyError:
            raise AppError(
                "TOOL_NOT_REGISTERED",
                f"Tool '{name}' is not registered. Available: {ToolRegistry.all_names()}",
                422,
            )

    agent = Agent(
        organization_id=ctx.org_id,
        created_by=ctx.user_id,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        provider=body.provider,
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        max_steps=body.max_steps,
        timeout_seconds=body.timeout_seconds,
        tool_names=body.tool_names,
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return success(AgentResponse.from_orm(agent).model_dump())


@router.get("")
async def list_agents(
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    stmt = select(Agent).where(Agent.organization_id == ctx.org_id)
    if active_only:
        stmt = stmt.where(Agent.is_active == True)  # noqa: E712
    stmt = stmt.order_by(Agent.created_at.desc())

    result = await db.execute(stmt)
    agents = result.scalars().all()
    return success([AgentResponse.from_orm(a).model_dump() for a in agents])


@router.get("/tools")
async def list_available_tools(
    ctx: TenantContext = Depends(require_role("member")),
):
    """Kayıtlı tool isimlerini ve tanımlarını listeler."""
    tools = []
    for name in ToolRegistry.all_names():
        handler = ToolRegistry.get(name)
        tools.append({
            "name": handler.name,
            "description": handler.description,
            "parameters": handler.parameters,
        })
    return success(tools)


@router.get("/{agent_id}")
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    agent = await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    return success(AgentResponse.from_orm(agent).model_dump())


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: uuid.UUID,
    body: UpdateAgentRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    agent = await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]

    if body.name is not None and body.name != agent.name:
        conflict = await db.execute(
            select(Agent).where(
                Agent.organization_id == ctx.org_id,
                Agent.name == body.name,
                Agent.id != agent_id,
            )
        )
        if conflict.scalar_one_or_none():
            raise AppError("AGENT_NAME_CONFLICT", f"An agent named '{body.name}' already exists.", 409)

    if body.tool_names is not None:
        for name in body.tool_names:
            try:
                ToolRegistry.get(name)
            except KeyError:
                raise AppError(
                    "TOOL_NOT_REGISTERED",
                    f"Tool '{name}' is not registered.",
                    422,
                )

    # description and max_tokens are nullable columns — allow explicit null.
    # All other Agent columns are NOT NULL; silently skip null values here so
    # a PATCH with {"name": null} doesn't crash the DB with a constraint error.
    _NULLABLE_FIELDS = {"description", "max_tokens"}
    update_fields = body.model_dump(exclude_unset=True)
    for field_name, value in update_fields.items():
        if value is None and field_name not in _NULLABLE_FIELDS:
            continue
        setattr(agent, field_name, value)
    agent.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(agent)
    return success(AgentResponse.from_orm(agent).model_dump())


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    agent = await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    await db.delete(agent)
    await db.commit()


# ─── Run ──────────────────────────────────────────────────

@router.post("/{agent_id}/run")
async def run_agent(
    agent_id: uuid.UUID,
    body: RunAgentRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("member")),
):
    """
    Agent'ı çalıştırır.

    stream=true (varsayılan): text/event-stream SSE döner.
    stream=false: tüm çalıştırma tamamlanınca JSON döner.
    """
    agent = await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    if not agent.is_active:
        raise AppError("AGENT_INACTIVE", "This agent is inactive.", 422)

    runner = await _build_runner(agent, ctx, db, redis)

    if body.stream:
        return StreamingResponse(
            _sse_generator(runner, body.input, agent.timeout_seconds),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Sync mode
    try:
        result = await asyncio.wait_for(
            runner.run(body.input),
            timeout=agent.timeout_seconds + 5,  # endpoint-level safety margin
        )
    except asyncio.TimeoutError:
        raise AppError("AGENT_TIMEOUT", f"Agent timed out after {agent.timeout_seconds}s.", 408)
    except AgentTimeoutError as exc:
        raise AppError(exc.code, exc.message, exc.status_code)
    except AgentMaxStepsError as exc:
        raise AppError(exc.code, exc.message, exc.status_code)
    except AgentError as exc:
        raise AppError(exc.code, exc.message, exc.status_code)
    except ProviderError as exc:
        raise AppError(exc.code, exc.message, exc.status_code)

    return success(RunAgentSyncResponse(
        trace_id=result.trace_id,
        content=result.content,
        steps_taken=result.steps_taken,
        finish_reason=result.finish_reason,
        total_usage=result.total_usage,
    ).model_dump())


async def _sse_generator(
    runner: AgentRunner,
    user_input: str,
    timeout_seconds: int,
):
    """
    SSE generator — runner.stream() event'lerini text/event-stream formatına çevirir.
    """
    timeout_at = asyncio.get_running_loop().time() + timeout_seconds + 5
    try:
        async for event in runner.stream(user_input):
            if asyncio.get_running_loop().time() > timeout_at:
                err = AgentTimeoutError(timeout_seconds)
                yield AgentStreamEvent(
                    type="error",
                    error_code=err.code,
                    error_message=err.message,
                ).to_sse()
                return
            yield event.to_sse()
    except Exception as exc:
        logger.error("sse_generator.error", error=str(exc))
        yield AgentStreamEvent(
            type="error",
            error_code="AGENT_UNEXPECTED_ERROR",
            error_message=str(exc),
        ).to_sse()
