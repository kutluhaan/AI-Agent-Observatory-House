"""
Conversations Router — Faz 1 (kalıcı sohbet thread'leri)

Agent-scoped, kullanıcıya özel sohbet thread'leri. Mesaj gönderince agent thread
hafızasıyla (önceki mesajlar) çalışır; asistan turu segments+trace ile kalıcı kaydedilir.

  GET    /agents/{agent_id}/conversations     — kullanıcının o agent'la thread'leri (member)
  POST   /agents/{agent_id}/conversations     — yeni thread (member)
  GET    /conversations/{id}                  — thread + mesajlar (owner)
  PATCH  /conversations/{id}                  — yeniden adlandır (owner)
  DELETE /conversations/{id}                  — sil (owner)
  POST   /conversations/{id}/messages         — mesaj ekle + agent çalıştır (SSE/JSON)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.api.v1.agents import _build_runner, _get_agent_or_404
from app.core.database import AsyncSessionLocal, get_db
from app.core.redis import get_redis
from app.core.responses import AppError, NotFoundError, success
from app.models.conversation import Conversation, ConversationMessage
from app.schemas.conversations import (
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    MessageResponse,
    PostMessageRequest,
    RenameConversationRequest,
)
from app.services.agent.base import AgentStreamEvent
from app.services.providers.base import Message

logger = structlog.get_logger()

# /conversations/* — thread detay + mesaj
router = APIRouter()
# /agents/{agent_id}/conversations — thread listesi/oluşturma
agent_conversations_router = APIRouter()

_HISTORY_LIMIT = 40  # token kontrolü için hafızaya beslenecek son mesaj sayısı


# ─── Helpers ──────────────────────────────────────────────

async def _get_conversation_or_404(
    conversation_id: uuid.UUID,
    ctx: TenantContext,
    db: AsyncSession,
) -> Conversation:
    """Owner + org kontrolü — başka kullanıcının/org'un thread'i 404."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == ctx.org_id,
            Conversation.user_id == ctx.user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError("CONVERSATION_NOT_FOUND", "Conversation not found.")
    return conv


def _make_title(text: str) -> str:
    line = text.strip().splitlines()[0] if text.strip() else "New chat"
    return (line[:60] + "…") if len(line) > 60 else line


def _accumulate(ev: AgentStreamEvent, segments: list[dict[str, Any]]) -> None:
    """SSE event'lerinden zengin segment listesi kur (frontend ile aynı yapı)."""
    if ev.type == "token" and ev.content:
        if segments and segments[-1]["kind"] == "text":
            segments[-1]["text"] += ev.content
        else:
            segments.append({"kind": "text", "text": ev.content})
    elif ev.type == "tool_call_start":
        segments.append({
            "kind": "tool",
            "tool": {
                "name": ev.tool_name,
                "args": ev.tool_arguments or {},
                "result": None,
                "status": "running",
            },
        })
    elif ev.type == "tool_call_end":
        for seg in reversed(segments):
            if (
                seg["kind"] == "tool"
                and seg["tool"]["name"] == ev.tool_name
                and seg["tool"]["status"] == "running"
            ):
                seg["tool"]["result"] = ev.tool_result
                seg["tool"]["status"] = "done"
                break


async def _persist_assistant(
    conversation_id: uuid.UUID,
    *,
    content: str,
    segments: list[dict[str, Any]],
    trace_id: str | None,
    error: str | None,
    seq: int,
    is_first: bool,
    title_seed: str,
) -> None:
    """Akış bittiğinde asistan turunu ve thread meta'sını taze bir session ile yazar."""
    async with AsyncSessionLocal() as db:
        db.add(ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            segments=segments,
            trace_id=trace_id,
            error=error,
            seq=seq,
        ))
        conv = await db.get(Conversation, conversation_id)
        if conv is not None:
            conv.last_message_at = datetime.now(UTC)
            if is_first and conv.title in ("New chat", "", None):
                conv.title = _make_title(title_seed)
        await db.commit()


# ─── Thread listesi / oluşturma (/agents/{id}/conversations) ───

@agent_conversations_router.get("/{agent_id}/conversations")
async def list_conversations(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    stmt = (
        select(Conversation, func.count(ConversationMessage.id))
        .outerjoin(ConversationMessage, ConversationMessage.conversation_id == Conversation.id)
        .where(
            Conversation.agent_id == agent_id,
            Conversation.organization_id == ctx.org_id,
            Conversation.user_id == ctx.user_id,
        )
        .group_by(Conversation.id)
        .order_by(Conversation.last_message_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return success([
        ConversationSummary.from_orm(conv, message_count=count).model_dump()
        for conv, count in rows
    ])


@agent_conversations_router.post("/{agent_id}/conversations", status_code=201)
async def create_conversation(
    agent_id: uuid.UUID,
    body: CreateConversationRequest = CreateConversationRequest(),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    conv = Conversation(
        organization_id=ctx.org_id,
        agent_id=agent_id,
        user_id=ctx.user_id,
        title=body.title or "New chat",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return success(ConversationSummary.from_orm(conv, message_count=0).model_dump())


# ─── Thread detay / yeniden adlandır / sil (/conversations/{id}) ───

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    conv = await _get_conversation_or_404(conversation_id, ctx, db)
    msgs = (await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.seq, ConversationMessage.created_at)
    )).scalars().all()

    return success(ConversationDetail(
        id=conv.id,
        agent_id=conv.agent_id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        messages=[MessageResponse.from_orm(m) for m in msgs],
    ).model_dump())


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: uuid.UUID,
    body: RenameConversationRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    conv = await _get_conversation_or_404(conversation_id, ctx, db)
    conv.title = body.title
    await db.commit()
    return success(ConversationSummary.from_orm(conv).model_dump())


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    conv = await _get_conversation_or_404(conversation_id, ctx, db)
    await db.delete(conv)
    await db.commit()


# ─── Mesaj gönder + agent çalıştır (/conversations/{id}/messages) ───

@router.post("/{conversation_id}/messages")
async def post_message(
    conversation_id: uuid.UUID,
    body: PostMessageRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("member")),
):
    conv = await _get_conversation_or_404(conversation_id, ctx, db)
    agent = await _get_agent_or_404(conv.agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    if not agent.is_active:
        raise AppError("AGENT_INACTIVE", "This agent is inactive.", 422)

    # Geçmiş (hafıza) — yeni mesajdan ÖNCEKİ mesajlar
    existing = (await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.seq, ConversationMessage.created_at)
    )).scalars().all()

    history = [
        Message(role=m.role, content=m.content)
        for m in existing[-_HISTORY_LIMIT:]
        if m.content
    ]
    is_first = len(existing) == 0
    user_seq = len(existing)

    # Runner'ı ÖNCE kur (provider/tool doğrulaması) — başarısızsa user mesajı yazma
    runner = await _build_runner(agent, ctx, db, redis, history=history)

    # Kullanıcı mesajını kalıcı yaz
    db.add(ConversationMessage(
        conversation_id=conversation_id,
        role="user",
        content=body.input,
        seq=user_seq,
    ))
    conv.last_message_at = datetime.now(UTC)
    await db.commit()

    if body.stream:
        return StreamingResponse(
            _stream_and_persist(
                runner, body.input, conversation_id,
                is_first=is_first, seq=user_seq + 1, timeout_seconds=agent.timeout_seconds,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Sync mod
    result = await runner.run(body.input)
    await _persist_assistant(
        conversation_id,
        content=result.content,
        segments=[{"kind": "text", "text": result.content}],
        trace_id=result.trace_id,
        error=None,
        seq=user_seq + 1,
        is_first=is_first,
        title_seed=body.input,
    )
    return success({
        "trace_id": result.trace_id,
        "content": result.content,
        "steps_taken": result.steps_taken,
        "finish_reason": result.finish_reason,
    })


async def _stream_and_persist(
    runner,
    user_input: str,
    conversation_id: uuid.UUID,
    *,
    is_first: bool,
    seq: int,
    timeout_seconds: int,
):
    """runner.stream()'i SSE'ye çevirir + asistan turunu biterken kalıcı yazar."""
    from app.services.hitl import HITL_TIMEOUT

    segments: list[dict[str, Any]] = []
    content_parts: list[str] = []
    trace_id: str | None = None
    error: str | None = None
    timeout_at = asyncio.get_running_loop().time() + timeout_seconds + 5

    try:
        async for ev in runner.stream(user_input):
            _accumulate(ev, segments)
            if ev.type == "token" and ev.content:
                content_parts.append(ev.content)
            elif ev.type == "done":
                trace_id = ev.trace_id
            elif ev.type == "error":
                error = ev.error_message or ev.error_code
            yield ev.to_sse()
            if ev.type == "hitl_requested":
                timeout_at += HITL_TIMEOUT
            if asyncio.get_running_loop().time() > timeout_at:
                error = error or "Agent timed out."
                yield AgentStreamEvent(
                    type="error", error_code="AGENT_TIMEOUT", error_message="Agent timed out.",
                ).to_sse()
                break
    except Exception as exc:  # noqa: BLE001
        logger.error("conversation.stream_error", error=str(exc))
        error = str(exc)
        yield AgentStreamEvent(
            type="error", error_code="AGENT_UNEXPECTED_ERROR", error_message=str(exc),
        ).to_sse()
    finally:
        await _persist_assistant(
            conversation_id,
            content="".join(content_parts),
            segments=segments,
            trace_id=trace_id,
            error=error,
            seq=seq,
            is_first=is_first,
            title_seed=user_input,
        )
