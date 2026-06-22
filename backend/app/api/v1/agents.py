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
from app.core.encryption import encrypt_value
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
    HITLRejectedError,
    HITLTimeoutError,
)
from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.runner import AgentRunner
from app.services.agent.tools.files import DESTRUCTIVE_FILE_TOOLS, FILE_TOOL_NAMES
from app.services.agent.tools.skills import SKILL_TOOL_NAMES
from app.services.agent import file_store, knowledge_store
from app.services.hitl import get_hitl_engine
from app.services.providers.base import ProviderError
from app.services.providers.factory import get_provider_for_agent
from app.services.trace_collector import Tracer
from app.ws.traces import manager as ws_manager

logger = structlog.get_logger()
router = APIRouter()

# Tüm agent yanıtları Markdown formatında — UI bunu zengin biçimde render eder
_MARKDOWN_INSTRUCTION = (
    "Format every response using GitHub-Flavored Markdown: use headings, **bold**, "
    "*italics*, bullet/numbered lists, tables, `inline code`, fenced code blocks with a "
    "language tag, blockquotes and links where they make the answer clearer. When you write "
    "files, write their content in Markdown too. Keep the structure clean and readable."
)


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
    history: list | None = None,
) -> AgentRunner:
    effective_tools = list(agent.tool_names or [])

    # ask_user kullanıcıya doğrudan soru sorar — onay (HITL) gerektirmez
    hitl_names = [n for n in (agent.hitl_tool_names or []) if n != "ask_user"]

    # Dosya sistemi açıksa file tool'ları otomatik eklenir (DB'de saklanmaz).
    # Yıkıcı dosya tool'ları (sil/düzenle/klasör-sil) varsayılan olarak onaydan geçer.
    if agent.file_system_enabled:
        effective_tools += FILE_TOOL_NAMES
        for t in DESTRUCTIVE_FILE_TOOLS:
            if t not in hitl_names:
                hitl_names.append(t)

    # Faz 4: bilgi öğeleri — kurallar/anayasa system prompt'a, skill'ler tool ile
    system_prompt = agent.system_prompt
    always_on = await knowledge_store.load_always_on(db, agent.id)
    if always_on:
        system_prompt = f"{system_prompt}\n\n{always_on}"
    if await knowledge_store.has_skills(db, agent.id):
        effective_tools += SKILL_TOOL_NAMES
        system_prompt += (
            "\n\nYou have skills available. Call list_skills to discover them and "
            "read_skill to read one before a task it covers."
        )

    # Tüm yanıtlar Markdown — UI zengin biçimde gösterir
    system_prompt = f"{system_prompt}\n\n{_MARKDOWN_INSTRUCTION}"

    config = AgentConfig(
        agent_id=agent.id,
        org_id=ctx.org_id,  # type: ignore[arg-type]
        name=agent.name,
        system_prompt=system_prompt,
        provider=agent.provider,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        max_steps=agent.max_steps,
        timeout_seconds=agent.timeout_seconds,
        tool_names=effective_tools,
        hitl_tool_names=hitl_names,
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
        provider = await get_provider_for_agent(db, agent)
    except AppError:
        raise

    # F7.2: agent'ın MCP tool'larını çözümle (uzak sunucu URL/key dahil)
    from app.services.mcp.resolver import resolve_agent_mcp_tools
    mcp_tools = await resolve_agent_mcp_tools(db, agent)

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
        agent_id=agent.id,
        user_id=ctx.user_id,  # G1: Gmail gibi per-user tool'lar için
    )

    try:
        hitl = get_hitl_engine()
    except RuntimeError:
        hitl = None  # HITL engine başlatılmamışsa (test ortamı) None

    return AgentRunner(
        config=config,
        provider=provider,
        tracer=tracer,
        tool_context=tool_context,
        hitl=hitl,
        ws_manager=ws_manager,
        history=history,
        mcp_tools=mcp_tools,
    )


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

    # Kayıtsız tool varsa erken hata; file/skill tool'ları otomatik yönetilir
    for name in body.tool_names:
        if name in FILE_TOOL_NAMES or name in SKILL_TOOL_NAMES:
            raise AppError(
                "TOOL_AUTO_MANAGED",
                f"'{name}' is added automatically (file system / skills) — do not select it manually.",
                422,
            )
        try:
            ToolRegistry.get(name)
        except KeyError:
            raise AppError(
                "TOOL_NOT_REGISTERED",
                f"Tool '{name}' is not registered. Available: {ToolRegistry.all_names()}",
                422,
            )

    # hitl_tool_names, tool_names'ın alt kümesi olmalı
    for name in body.hitl_tool_names:
        if name not in body.tool_names:
            raise AppError(
                "HITL_TOOL_NOT_IN_TOOL_NAMES",
                f"hitl_tool_name '{name}' must also be in tool_names.",
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
        hitl_tool_names=body.hitl_tool_names,
        file_system_enabled=body.file_system_enabled,
        is_active=True,
        endpoint_url=(body.endpoint_url or None),
        endpoint_api_key=encrypt_value(body.endpoint_api_key) if body.endpoint_api_key else None,
        mcp_tools=body.mcp_tools or None,
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
    """Seçilebilir tool'ları listeler (kategori bilgisiyle). File/skill tool'ları
    auto-managed; internal tool'lar (echo/calculator vb.) gizli — hariç tutulur."""
    from app.services.agent.tool_categories import INTERNAL_TOOLS, category_of

    tools = []
    for name in ToolRegistry.all_names():
        if name in FILE_TOOL_NAMES or name in SKILL_TOOL_NAMES or name in INTERNAL_TOOLS:
            continue
        handler = ToolRegistry.get(name)
        tools.append({
            "name": handler.name,
            "description": handler.description,
            "parameters": handler.parameters,
            "category": category_of(name),
        })
    return success(tools)


@router.get("/tool-categories")
async def list_tool_categories(
    ctx: TenantContext = Depends(require_role("member")),
):
    """Tool'ları kategoriler halinde döner (F2): file/web/self/finance/operation.

    Her kategori: {key, label, note, managed_by_file_system, coming_soon, tools[]}.
    """
    from app.services.agent.tool_categories import build_categories

    return success(build_categories())


@router.get("/{agent_id}")
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    agent = await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    return success(AgentResponse.from_orm(agent).model_dump())


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """F5.1: Agent'ın tüm test run'larındaki case sonuçlarından toplu performans.

    Canlı hesaplanır (TestCaseResult → TestCase.agent_id eşleşmesi). Kalıcı veriden;
    çıkış/giriş yapsan da agent paneli orada olur.
    """
    from app.models.test_suite import TestCase, TestCaseResult, TestRun
    from app.services.test_suite.agent_stats import compute_agent_stats

    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    rows = (await db.execute(
        select(TestCaseResult)
        .join(TestCase, TestCaseResult.case_id == TestCase.id)
        .join(TestRun, TestCaseResult.run_id == TestRun.id)
        .where(
            TestCase.agent_id == agent_id,
            TestRun.organization_id == ctx.org_id,
        )
    )).scalars().all()
    return success(compute_agent_stats(list(rows)))


# ─── Dosya gezgini (salt-okunur, Faz 3) ──────────────────

@router.get("/{agent_id}/files")
async def list_agent_files(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Agent'ın dosya sistemindeki tüm dosya/klasörleri listeler (ağaç UI'da kurulur)."""
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    files = await file_store.list_all(db, agent_id)
    return success([
        {
            "path": f.path,
            "is_dir": f.is_dir,
            "size_bytes": f.size_bytes,
            "updated_at": f.updated_at.isoformat(),
        }
        for f in files
    ])


@router.get("/{agent_id}/files/content")
async def get_agent_file_content(
    agent_id: uuid.UUID,
    path: str = Query(...),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Tek bir dosyanın içeriğini döner (görüntüleme/indirme için)."""
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    f = await file_store.get_one(db, agent_id, path)
    if f is None or f.is_dir:
        raise NotFoundError("FILE_NOT_FOUND", "File not found.")
    return success({"path": f.path, "content": f.content or "", "size_bytes": f.size_bytes})


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
            if name in FILE_TOOL_NAMES or name in SKILL_TOOL_NAMES:
                raise AppError(
                    "TOOL_AUTO_MANAGED",
                    f"'{name}' is added automatically (file system / skills).",
                    422,
                )
            try:
                ToolRegistry.get(name)
            except KeyError:
                raise AppError(
                    "TOOL_NOT_REGISTERED",
                    f"Tool '{name}' is not registered.",
                    422,
                )

    # hitl_tool_names, nihai tool_names'ın alt kümesi olmalı
    if body.hitl_tool_names is not None:
        effective_tool_names = body.tool_names if body.tool_names is not None else (agent.tool_names or [])
        for name in body.hitl_tool_names:
            if name not in effective_tool_names:
                raise AppError(
                    "HITL_TOOL_NOT_IN_TOOL_NAMES",
                    f"hitl_tool_name '{name}' must also be in tool_names.",
                    422,
                )

    # description and max_tokens are nullable columns — allow explicit null.
    # All other Agent columns are NOT NULL; silently skip null values here so
    # a PATCH with {"name": null} doesn't crash the DB with a constraint error.
    _NULLABLE_FIELDS = {"description", "max_tokens", "endpoint_url", "mcp_tools"}
    update_fields = body.model_dump(exclude_unset=True)
    # F7.1: endpoint_api_key özel — şifrele; boş/None → temizle
    if "endpoint_api_key" in update_fields:
        raw_key = update_fields.pop("endpoint_api_key")
        agent.endpoint_api_key = encrypt_value(raw_key) if raw_key else None
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

    # Sync mode — HITL beklemesi olabilecek agent'lara 10 dk ekstra (runner.run() ile senkron)
    from app.services.hitl import HITL_TIMEOUT
    hitl_extra = HITL_TIMEOUT if agent.hitl_tool_names else 0
    try:
        result = await asyncio.wait_for(
            runner.run(body.input),
            timeout=agent.timeout_seconds + hitl_extra + 5,  # endpoint-level safety margin
        )
    except asyncio.TimeoutError:
        raise AppError("AGENT_TIMEOUT", f"Agent timed out after {agent.timeout_seconds}s.", 408)
    except AgentTimeoutError as exc:
        raise AppError(exc.code, exc.message, exc.status_code)
    except AgentMaxStepsError as exc:
        raise AppError(exc.code, exc.message, exc.status_code)
    except (HITLRejectedError, HITLTimeoutError) as exc:
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
    from app.services.hitl import HITL_TIMEOUT
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
            # Her HITL/ask_user bekleme penceresi için timeout'u uzat
            if event.type in ("hitl_requested", "ask_user_requested"):
                timeout_at += HITL_TIMEOUT
    except Exception as exc:
        logger.error("sse_generator.error", error=str(exc))
        yield AgentStreamEvent(
            type="error",
            error_code="AGENT_UNEXPECTED_ERROR",
            error_message=str(exc),
        ).to_sse()
