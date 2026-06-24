"""
Notification Channels Router — Mesajlaşma (loop it.4)

Org-bazlı bildirim kanalı (generic webhook). URL şifreli saklanır, ham dönmez.

  POST   /notification-channels            — ekle (admin)
  GET    /notification-channels            — listele (member)
  DELETE /notification-channels/{id}       — sil (admin)
  POST   /notification-channels/{id}/test  — test mesajı gönder (member)
"""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.encryption import decrypt_value, encrypt_value
from app.core.responses import AppError, NotFoundError, success
from app.models.notification import NotificationChannel
from app.services.agent.tools.notify import send_webhook

router = APIRouter()


class CreateChannelRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    url: Annotated[str, Field(min_length=8, max_length=2000)]


class ChannelResponse(BaseModel):
    id: uuid.UUID
    name: str
    channel_type: str
    is_active: bool
    created_at: str

    @classmethod
    def from_orm(cls, c: Any) -> "ChannelResponse":
        return cls(id=c.id, name=c.name, channel_type=c.channel_type,
                   is_active=c.is_active, created_at=c.created_at.isoformat())


async def _get_or_404(cid: uuid.UUID, org_id, db: AsyncSession) -> NotificationChannel:
    row = (await db.execute(
        select(NotificationChannel).where(NotificationChannel.id == cid, NotificationChannel.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("CHANNEL_NOT_FOUND", "Notification channel not found.")
    return row


@router.post("", status_code=201)
async def create_channel(body: CreateChannelRequest, db: AsyncSession = Depends(get_db),
                         ctx: TenantContext = Depends(require_role("admin"))):
    dup = (await db.execute(select(NotificationChannel).where(
        NotificationChannel.organization_id == ctx.org_id, NotificationChannel.name == body.name))).scalar_one_or_none()
    if dup:
        raise AppError("CHANNEL_NAME_CONFLICT", f"A channel named '{body.name}' already exists.", 409)
    ch = NotificationChannel(id=uuid.uuid4(), organization_id=ctx.org_id, name=body.name,
                             channel_type="webhook", encrypted_url=encrypt_value(body.url))
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return success(ChannelResponse.from_orm(ch).model_dump())


@router.get("")
async def list_channels(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    rows = (await db.execute(select(NotificationChannel).where(
        NotificationChannel.organization_id == ctx.org_id).order_by(NotificationChannel.created_at.desc()))).scalars().all()
    return success([ChannelResponse.from_orm(c).model_dump() for c in rows])


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         ctx: TenantContext = Depends(require_role("admin"))):
    ch = await _get_or_404(channel_id, ctx.org_id, db)
    await db.delete(ch)
    await db.commit()


@router.post("/{channel_id}/test")
async def test_channel(channel_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       ctx: TenantContext = Depends(require_role("member"))):
    ch = await _get_or_404(channel_id, ctx.org_id, db)
    ok, detail = await send_webhook(decrypt_value(ch.encrypted_url), "✅ Test bildirimi — AI Agent Observatory")
    if not ok:
        raise AppError("CHANNEL_TEST_FAILED", f"Webhook failed: {detail}", 502)
    return success({"ok": True})
