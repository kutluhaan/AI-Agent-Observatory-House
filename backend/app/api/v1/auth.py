"""
Auth Router — M3 + M4

M3: register, login, logout, me
M4: refresh, switch-org, verify-email, resend-verification
M5'te eklenecekler: org endpoints
"""
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, get_current_user

from app.core.config import get_settings
from app.core.database import get_db
from app.core.email import send_verification_email
from app.core.redis import get_redis
from app.core.responses import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    success,
)
from app.models.auth import EmailVerification, RefreshToken
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    SwitchOrgRequest,
    VerifyEmailRequest,
)
from app.services import jwt_service
from app.services.password_service import hash_password, validate_password_strength, verify_password
from app.services.token_store import (
    blacklist_access_token,
    check_rate_limit,
    consume_refresh_token,
    get_email_verify_user,
    get_refresh_token_user,
    revoke_email_verify_token,
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


async def get_active_orgs(db: AsyncSession, user_id: uuid.UUID) -> list[OrganizationMember]:
    """Aktif org üyelikleri — en eski joined_at önce (login/refresh fallback için deterministik)."""
    result = await db.execute(
        select(OrganizationMember)
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization.has(Organization.is_active.is_(True)),
        )
        .options(selectinload(OrganizationMember.organization))
        .order_by(OrganizationMember.joined_at.asc())
    )
    return list(result.scalars().all())


def resolve_active_org(
    active_orgs: list[OrganizationMember],
    preferred_org_id: uuid.UUID | None,
) -> OrganizationMember | None:
    """Refresh sırasında geçerli access token org'u korunur; değilse ilk aktif org."""
    if preferred_org_id:
        for membership in active_orgs:
            if membership.organization_id == preferred_org_id:
                return membership
    return active_orgs[0] if active_orgs else None


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

    await send_verification_email(user.email, raw_token)

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

    active_orgs = await get_active_orgs(db, user.id)
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


# ─── POST /auth/refresh ───────────────────────────────────

@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    if not refresh_token:
        raise UnauthorizedError("INVALID_TOKEN", "Refresh token missing.")

    try:
        payload = jwt_service.decode_refresh_token(refresh_token)
    except UnauthorizedError:
        raise

    allowed, retry_after = await check_rate_limit(redis, "refresh", payload["sub"])
    if not allowed:
        raise RateLimitError(retry_after)

    jti = payload["jti"]
    if not await get_refresh_token_user(redis, jti):
        raise UnauthorizedError("REFRESH_TOKEN_REVOKED", "Refresh token has been revoked.")

    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("INVALID_TOKEN", "User not found or disabled.")

    old_token_hash = jwt_service.hash_token(refresh_token)

    rt_result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == old_token_hash,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    old_rt = rt_result.scalar_one_or_none()
    if not old_rt:
        raise UnauthorizedError("REFRESH_TOKEN_REVOKED", "Refresh token has been revoked.")

    old_rt.is_revoked = True
    old_rt.revoked_at = datetime.now(UTC)

    preferred_org_id: uuid.UUID | None = None
    if access_token:
        try:
            access_payload = jwt_service.decode_access_token(access_token)
            raw_org_id = access_payload.get("org_id")
            if raw_org_id:
                preferred_org_id = uuid.UUID(raw_org_id)
        except UnauthorizedError:
            pass

    active_orgs = await get_active_orgs(db, user.id)
    chosen_org = resolve_active_org(active_orgs, preferred_org_id)

    new_access = jwt_service.create_access_token(
        user_id=user.id,
        email=user.email,
        org_id=chosen_org.organization_id if chosen_org else None,
        org_slug=chosen_org.organization.slug if chosen_org else None,
        role=chosen_org.role if chosen_org else None,
    )
    new_raw_refresh, new_jti = jwt_service.create_refresh_token(user.id)
    new_token_hash = jwt_service.hash_token(new_raw_refresh)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            device_info=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
    )
    await db.commit()

    # Redis: eski jti atomik tüket (commit sonrası), sonra yeni jti yaz
    await consume_refresh_token(redis, jti)
    await store_refresh_token(redis, new_jti, str(user.id))
    _set_auth_cookies(response, new_access, new_raw_refresh)

    return success({"message": "Token refreshed."})


# ─── POST /auth/switch-org ────────────────────────────────

@router.post("/switch-org")
async def switch_org(
    body: SwitchOrgRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
):
    allowed, retry_after = await check_rate_limit(redis, "switch_org", str(current_user.user_id))
    if not allowed:
        raise RateLimitError(retry_after)

    org_result = await db.execute(select(Organization).where(Organization.id == body.org_id))
    org = org_result.scalar_one_or_none()
    if not org:
        raise NotFoundError("ORGANIZATION_NOT_FOUND", "Organization not found.")

    member_result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.user_id,
            OrganizationMember.organization_id == body.org_id,
        )
    )
    membership = member_result.scalar_one_or_none()
    if not membership:
        raise ForbiddenError("NOT_A_MEMBER", "You are not a member of this organization.")

    if not org.is_active:
        raise ForbiddenError("ORG_DEACTIVATED", "This organization has been deactivated.")

    new_access = jwt_service.create_access_token(
        user_id=current_user.user_id,
        email=current_user.email,
        org_id=org.id,
        org_slug=org.slug,
        role=membership.role,
    )

    is_prod = settings.is_production
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )

    return success({
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
        },
        "role": membership.role,
    })


# ─── POST /auth/verify-email ──────────────────────────────

@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    token_hash = jwt_service.hash_token(body.token)

    redis_user_id = await get_email_verify_user(redis, token_hash)
    if not redis_user_id:
        raise AppError(
            "EMAIL_VERIFICATION_EXPIRED",
            "Verification link is invalid or has expired.",
            410,
        )

    result = await db.execute(
        select(EmailVerification).where(
            EmailVerification.token_hash == token_hash,
            EmailVerification.used_at.is_(None),
        )
    )
    verification = result.scalar_one_or_none()

    if (
        not verification
        or verification.expires_at < datetime.now(UTC)
        or str(verification.user_id) != redis_user_id
    ):
        raise AppError(
            "EMAIL_VERIFICATION_EXPIRED",
            "Verification link is invalid or has expired.",
            410,
        )

    verification.used_at = datetime.now(UTC)
    await db.execute(
        sa_update(User)
        .where(User.id == verification.user_id)
        .values(is_verified=True)
    )
    await db.commit()

    await revoke_email_verify_token(redis, token_hash)

    return success({"message": "Email verified successfully."})


# ─── POST /auth/resend-verification ───────────────────────

@router.post("/resend-verification")
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    allowed, retry_after = await check_rate_limit(redis, "resend_verify", body.email)
    if not allowed:
        raise RateLimitError(retry_after)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and not user.is_verified and user.is_active:
        await db.execute(
            sa_update(EmailVerification)
            .where(
                EmailVerification.user_id == user.id,
                EmailVerification.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )

        raw_token = jwt_service.generate_secure_token()
        token_hash = jwt_service.hash_token(raw_token)
        db.add(
            EmailVerification(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        await db.commit()

        await store_email_verify_token(redis, token_hash, str(user.id))
        await send_verification_email(user.email, raw_token)

    return success({"message": "If this email exists, a verification link has been sent."})


@router.get("/me")
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user.user_id))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("USER_NOT_FOUND", "User not found.")

    active_orgs = await get_active_orgs(db, user.user_id)

    # Aktif org context'i — token'dan gelir (org_id/org_slug/role); org_name DB'den.
    active_org_name = None
    if user.org_id:
        for m in active_orgs:
            if m.organization_id == user.org_id:
                active_org_name = m.organization.name
                break

    return success({
        "id": str(db_user.id),
        "email": db_user.email,
        "full_name": db_user.full_name,
        "is_verified": db_user.is_verified,
        "avatar_url": db_user.avatar_url,
        "org_id": str(user.org_id) if user.org_id else None,
        "org_name": active_org_name,
        "org_slug": user.org_slug,
        "role": user.role,
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
