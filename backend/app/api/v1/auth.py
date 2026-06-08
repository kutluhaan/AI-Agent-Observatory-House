"""
Auth Router — M3 kapsamı: register, login, logout, me.

M4'te eklenecekler: refresh, switch-org, verify-email, resend-verification
M5'te eklenecekler: org endpoints
"""
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, get_current_user

from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.responses import (
    ConflictError,
    ForbiddenError,
    RateLimitError,
    UnauthorizedError,
    success,
    NotFoundError,
)
from app.models.auth import EmailVerification, RefreshToken
from app.models.organization import OrganizationMember
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import jwt_service
from app.services.password_service import hash_password, validate_password_strength, verify_password
from app.services.token_store import (
    blacklist_access_token,
    check_rate_limit,
    revoke_refresh_token,
    store_email_verify_token,
    store_refresh_token,
)

router = APIRouter()
settings = get_settings()


# ─── Cookie Yardımcıları ──────────────────────────────────

def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """
    httpOnly cookie'leri set eder.
    secure=True sadece production'da — development'ta HTTP ile de çalışır.
    refresh_token path=/auth/refresh — başka endpoint'ler görmez.
    """
    is_prod = settings.is_production
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")


# ─── POST /auth/register ──────────────────────────────────

@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Rate limit — IP bazlı
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await check_rate_limit(redis, "register", client_ip)
    if not allowed:
        raise RateLimitError(retry_after)

    # Email unique kontrolü
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise ConflictError("EMAIL_ALREADY_EXISTS", "An account with this email already exists.")

    # Şifre validasyon + hash
    validate_password_strength(body.password)
    password_hash = hash_password(body.password)

    # User oluştur
    user = User(
        email=body.email,
        password_hash=password_hash,
        full_name=body.full_name,
        is_verified=False,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # id üretilsin ama commit etme

    # Email verification token
    raw_token = jwt_service.generate_secure_token()
    token_hash = jwt_service.hash_token(raw_token)

    verification = EmailVerification(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(verification)
    await db.commit()

    # Redis'e yaz
    await store_email_verify_token(redis, token_hash, str(user.id))

    # TODO: M4 — email servisi entegrasyonu (Resend)
    # await email_service.send_verification(user.email, raw_token)

    return success({
        "message": "Registration successful. Please verify your email.",
        "user_id": str(user.id),
    })


# ─── POST /auth/login ─────────────────────────────────────

@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Rate limit — email bazlı
    allowed, retry_after = await check_rate_limit(redis, "login", body.email)
    if not allowed:
        raise RateLimitError(retry_after)

    # User lookup
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Şifre kontrolü — user yoksa veya şifre yanlışsa AYNI hata (enumeration koruması)
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError(
            "INVALID_CREDENTIALS",
            "The email or password you entered is incorrect.",
        )

    # Ek kontroller — sıra önemli (spec'e göre)
    if not user.is_verified:
        raise ForbiddenError("EMAIL_NOT_VERIFIED", "Please verify your email before logging in.")

    if not user.is_active:
        raise ForbiddenError("ACCOUNT_DISABLED", "This account has been disabled.")

    # Kullanıcının org'larını getir (M3'te genellikle boş — org henüz yok)
    org_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .options(selectinload(OrganizationMember.organization))
    )
    memberships = org_result.scalars().all()
    active_orgs = [m for m in memberships if m.organization.is_active]
    first_org = active_orgs[0] if active_orgs else None

    # Token üret
    access_token = jwt_service.create_access_token(
        user_id=user.id,
        email=user.email,
        org_id=first_org.organization_id if first_org else None,
        org_slug=first_org.organization.slug if first_org else None,
        role=first_org.role if first_org else None,
    )
    raw_refresh, jti = jwt_service.create_refresh_token(user.id)
    token_hash = jwt_service.hash_token(raw_refresh)

    # DB'ye refresh token kaydet
    refresh_db = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        device_info=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(refresh_db)

    # last_login_at güncelle
    user.last_login_at = datetime.now(UTC)
    await db.commit()

    # Redis whitelist
    await store_refresh_token(redis, jti, str(user.id))

    # Cookie'leri set et
    _set_auth_cookies(response, access_token, raw_refresh)

    return success({
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
            "avatar_url": user.avatar_url,
        },
        "organizations": [
            {
                "id": str(m.organization.id),
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
            }
            for m in active_orgs
        ],
    })


# ─── POST /auth/logout ────────────────────────────────────

@router.post("/logout")
async def logout(
    response: Response,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    # Access token blacklist'e al
    if access_token:
        try:
            payload = jwt_service.decode_access_token(access_token)
            await blacklist_access_token(redis, payload["jti"])
        except Exception:
            pass  # Expire veya geçersiz — yine de cookie'leri sil

    # Refresh token revoke et
    if refresh_token:
        try:
            payload = jwt_service.decode_refresh_token(refresh_token)
            token_hash = jwt_service.hash_token(refresh_token)

            await revoke_refresh_token(redis, payload["jti"])

            # DB'de de revoke et
            result = await db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            rt = result.scalar_one_or_none()
            if rt:
                rt.is_revoked = True
                rt.revoked_at = datetime.now(UTC)
                await db.commit()
        except Exception:
            pass

    _clear_auth_cookies(response)
    return success({"message": "Logged out successfully."})


@router.get("/me")
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("USER_NOT_FOUND", "User not found.")

    org_result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.user_id)
        .options(selectinload(OrganizationMember.organization))
    )
    memberships = org_result.scalars().all()
    active_orgs = [m for m in memberships if m.organization.is_active]

    return success({
        "id": str(db_user.id),
        "email": db_user.email,
        "full_name": db_user.full_name,
        "is_verified": db_user.is_verified,
        "avatar_url": db_user.avatar_url,
        "organizations": [
            {
                "id": str(m.organization.id),
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
            }
            for m in active_orgs
        ],
    })
