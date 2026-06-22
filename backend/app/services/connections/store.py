"""
Servis bağlantısı saklama + token yenileme — G1

Token'lar Fernet ile şifreli saklanır. get_valid_access_token, süresi dolmuşsa
refresh_token ile yeniler ve kalıcı günceller.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value, encrypt_value
from app.models.connection import ServiceConnection
from app.services.connections import google_oauth


async def get_connection(db: AsyncSession, user_id, org_id, provider: str = "google") -> ServiceConnection | None:
    return (await db.execute(
        select(ServiceConnection).where(
            ServiceConnection.user_id == user_id,
            ServiceConnection.organization_id == org_id,
            ServiceConnection.provider == provider,
        )
    )).scalar_one_or_none()


def _expiry_from(expires_in: int | None) -> datetime | None:
    if not expires_in:
        return None
    return datetime.now(UTC) + timedelta(seconds=int(expires_in))


async def upsert_connection(
    db: AsyncSession, user_id, org_id, provider: str, token_data: dict, email: str | None,
) -> ServiceConnection:
    conn = await get_connection(db, user_id, org_id, provider)
    access = token_data.get("access_token", "")
    refresh = token_data.get("refresh_token")
    scopes = token_data.get("scope")
    expiry = _expiry_from(token_data.get("expires_in"))

    if conn is None:
        conn = ServiceConnection(
            id=uuid.uuid4(), user_id=user_id, organization_id=org_id, provider=provider,
        )
        db.add(conn)
    conn.account_email = email or conn.account_email
    conn.encrypted_access_token = encrypt_value(access)
    if refresh:  # refresh_token sadece ilk consent'te gelir; varsa güncelle
        conn.encrypted_refresh_token = encrypt_value(refresh)
    conn.scopes = scopes or conn.scopes
    conn.token_expiry = expiry
    conn.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(conn)
    return conn


async def get_valid_access_token(db: AsyncSession, user_id, org_id, provider: str = "google") -> str | None:
    """Geçerli access token döner; süresi dolmuşsa refresh ile yeniler ve saklar. Yoksa None."""
    conn = await get_connection(db, user_id, org_id, provider)
    if conn is None:
        return None

    expiring = conn.token_expiry is not None and datetime.now(UTC) >= (conn.token_expiry - timedelta(seconds=60))
    if expiring and conn.encrypted_refresh_token:
        try:
            new = await google_oauth.refresh_access_token(decrypt_value(conn.encrypted_refresh_token))
            conn.encrypted_access_token = encrypt_value(new.get("access_token", ""))
            conn.token_expiry = _expiry_from(new.get("expires_in"))
            conn.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(conn)
        except Exception:
            return None
    return decrypt_value(conn.encrypted_access_token)
