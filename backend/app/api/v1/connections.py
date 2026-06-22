"""
Connections Router — G1 (kullanıcı OAuth bağlantıları, Gmail)

  GET    /connections                      — kullanıcının bağlantıları (member)
  POST   /connections/google/authorize     — Google consent URL'i üret (member)
  GET    /connections/google/callback      — Google redirect; kodu token'a çevir, sakla
  DELETE /connections/google               — bağlantıyı sil (member)
"""
import uuid

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.core.encryption import decrypt_value
from app.core.redis import get_redis
from app.core.responses import AppError, success
from app.models.connection import ServiceConnection
from app.services.connections import google_oauth, store

settings = get_settings()
router = APIRouter()

_STATE_PREFIX = "gconn_state:"
_STATE_TTL = 600  # 10 dk


@router.get("")
async def list_connections(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    rows = (await db.execute(
        select(ServiceConnection).where(
            ServiceConnection.user_id == ctx.user_id,
            ServiceConnection.organization_id == ctx.org_id,
        )
    )).scalars().all()
    return success([
        {
            "provider": c.provider,
            "account_email": c.account_email,
            "scopes": (c.scopes or "").split(),
            "connected_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in rows
    ])


@router.post("/google/authorize")
async def google_authorize(
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("member")),
):
    if not google_oauth.is_configured():
        raise AppError("GOOGLE_NOT_CONFIGURED", "GOOGLE_CLIENT_ID/SECRET .env'de ayarlı değil.", 400)
    nonce = uuid.uuid4().hex
    await redis.set(f"{_STATE_PREFIX}{nonce}", f"{ctx.user_id}:{ctx.org_id}", ex=_STATE_TTL)
    return success({"authorize_url": google_oauth.build_authorize_url(nonce)})


@router.get("/google/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Google buraya yönlendirir (tarayıcı). State Redis'ten doğrulanır; auth cookie'ye güvenmez."""
    fe = settings.frontend_url.rstrip("/")
    if error or not code or not state:
        return RedirectResponse(f"{fe}/connections?google=error", status_code=302)

    raw = await redis.get(f"{_STATE_PREFIX}{state}")
    if not raw:
        return RedirectResponse(f"{fe}/connections?google=expired", status_code=302)
    await redis.delete(f"{_STATE_PREFIX}{state}")
    val = raw.decode() if isinstance(raw, bytes) else raw
    user_id, org_id = val.split(":")

    try:
        token_data = await google_oauth.exchange_code(code)
        email = await google_oauth.get_account_email(token_data.get("access_token", ""))
        await store.upsert_connection(
            db, uuid.UUID(user_id), uuid.UUID(org_id), "google", token_data, email,
        )
    except Exception:
        return RedirectResponse(f"{fe}/connections?google=error", status_code=302)

    return RedirectResponse(f"{fe}/connections?google=connected", status_code=302)


@router.delete("/google", status_code=204)
async def google_disconnect(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    conn = await store.get_connection(db, ctx.user_id, ctx.org_id, "google")
    if conn is None:
        return
    # Google'da token'ı iptal etmeye çalış (best-effort)
    try:
        token = decrypt_value(conn.encrypted_refresh_token or conn.encrypted_access_token)
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post("https://oauth2.googleapis.com/revoke", params={"token": token})
    except Exception:
        pass
    await db.delete(conn)
    await db.commit()
