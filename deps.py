"""
FastAPI Dependencies

M3: CurrentUser, get_current_user
M5/M6: TenantContext, get_tenant_context, require_role, require_org
"""
import uuid
from dataclasses import dataclass
from typing import Literal, Optional

import redis.asyncio as aioredis
from fastapi import Cookie, Depends

from app.core.redis import get_redis
from app.core.responses import ForbiddenError, UnauthorizedError
from app.services import jwt_service
from app.services.token_store import is_access_token_blacklisted

# Role hiyerarşisi — yüksek index = daha fazla yetki
ROLE_HIERARCHY = ["member", "admin", "owner"]


# ─── M3: CurrentUser ──────────────────────────────────────

@dataclass
class CurrentUser:
    """
    Temel auth context — M3'ten beri kullanılıyor.
    get_current_user dependency'sinden döner.
    """
    user_id: uuid.UUID
    email: str
    jti: str


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    redis: aioredis.Redis = Depends(get_redis),
) -> CurrentUser:
    """
    Temel auth dependency.
    Token doğrular, blacklist kontrol eder, CurrentUser döner.
    """
    if not access_token:
        raise UnauthorizedError("INVALID_TOKEN", "Authentication required.")

    payload = jwt_service.decode_access_token(access_token)
    jti = payload.get("jti", "")

    if await is_access_token_blacklisted(redis, jti):
        raise UnauthorizedError("INVALID_TOKEN", "Token has been revoked.")

    return CurrentUser(
        user_id=uuid.UUID(payload["sub"]),
        email=payload["email"],
        jti=jti,
    )


# ─── M6: TenantContext ────────────────────────────────────

@dataclass
class TenantContext:
    """
    Org context dahil tam auth state.
    Spec'e göre: user_id, email, jti, org_id, org_slug, role

    org_id None = kullanıcının aktif org'u yok (personal mode)
    """
    user_id: uuid.UUID
    email: str
    jti: str
    org_id: Optional[uuid.UUID]
    org_slug: Optional[str]
    role: Optional[Literal["owner", "admin", "member"]]


async def get_tenant_context(
    access_token: str | None = Cookie(default=None),
    redis: aioredis.Redis = Depends(get_redis),
) -> TenantContext:
    """
    TenantContext dependency — token'dan org context dahil tüm bilgiyi çıkarır.
    Her request'te DB'ye gidilmez — token'dan okunur (spec trade-off).
    """
    if not access_token:
        raise UnauthorizedError("INVALID_TOKEN", "Authentication required.")

    payload = jwt_service.decode_access_token(access_token)
    jti = payload.get("jti", "")

    if await is_access_token_blacklisted(redis, jti):
        raise UnauthorizedError("INVALID_TOKEN", "Token has been revoked.")

    org_id_raw = payload.get("org_id")
    org_id = uuid.UUID(org_id_raw) if org_id_raw else None

    return TenantContext(
        user_id=uuid.UUID(payload["sub"]),
        email=payload["email"],
        jti=jti,
        org_id=org_id,
        org_slug=payload.get("org_slug"),
        role=payload.get("role"),
    )


def require_role(minimum_role: Literal["member", "admin", "owner"]):
    """
    RBAC dependency factory.

    Kullanım:
        @router.delete("/orgs/{id}")
        async def delete_org(ctx: TenantContext = Depends(require_role("owner"))):
            ...

    Spec: role hiyerarşisi owner > admin > member
    """
    async def dependency(
        ctx: TenantContext = Depends(get_tenant_context),
    ) -> TenantContext:
        if ctx.role is None:
            raise ForbiddenError(
                "INSUFFICIENT_PERMISSIONS",
                "An active organization context is required.",
            )

        user_level = ROLE_HIERARCHY.index(ctx.role) if ctx.role in ROLE_HIERARCHY else -1
        required_level = ROLE_HIERARCHY.index(minimum_role)

        if user_level < required_level:
            raise ForbiddenError(
                "INSUFFICIENT_PERMISSIONS",
                f"This action requires at least {minimum_role} role.",
            )

        return ctx

    return dependency


def require_org(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    """
    Org context zorunlu kılar.
    Org'suz kullanıcı org-scoped endpoint'lere erişemez.
    """
    if ctx.org_id is None:
        raise ForbiddenError(
            "INSUFFICIENT_PERMISSIONS",
            "An active organization is required for this action.",
        )
    return ctx
