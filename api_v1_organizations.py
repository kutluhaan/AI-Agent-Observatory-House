"""
Organizations Router — M5

Endpoint'ler:
  POST   /organizations                                  — org oluştur
  GET    /organizations/{org_id}                         — org bilgisi
  PATCH  /organizations/{org_id}                         — org güncelle
  DELETE /organizations/{org_id}                         — org sil (hard delete)
  GET    /organizations/{org_id}/members                 — üye listesi
  PATCH  /organizations/{org_id}/members/{user_id}       — rol değiştir
  DELETE /organizations/{org_id}/members/{user_id}       — üye çıkar
  POST   /organizations/{org_id}/invitations             — davet gönder
  DELETE /organizations/{org_id}/invitations/{inv_id}    — davet iptal
  POST   /invitations/{token}/accept                     — davet kabul

RBAC M6'dan gelir (require_role dependency factory).
"""
import re
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    CurrentUser,
    TenantContext,
    get_current_user,
    get_tenant_context,
    require_role,
)
from app.core.database import get_db
from app.core.email import send_invitation_email
from app.core.redis import get_redis
from app.core.responses import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    success,
)
from app.models.auth import OrganizationInvitation
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.organizations import (
    CreateInvitationRequest,
    CreateOrgRequest,
    UpdateMemberRoleRequest,
    UpdateOrgRequest,
)
from app.services import jwt_service
from app.services.token_store import (
    get_invite_id,
    revoke_invite_token,
    store_invite_token,
)

router = APIRouter()


# ─── POST /organizations ──────────────────────────────────

@router.post("", status_code=201)
async def create_organization(
    body: CreateOrgRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Org oluşturur. Oluşturan kullanıcı otomatik owner olur.
    Slug unique ve değiştirilemez.
    """
    # Slug format kontrolü — UPPERCASE reddedilir (schema lowercase'e çevirmiyor, validate eder)
    import re as _re
    if not _re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', body.slug) and len(body.slug) > 1:
        raise AppError("INVALID_SLUG_FORMAT", "Slug must contain only lowercase letters, numbers, and hyphens.", 422)
    if body.slug != body.slug.lower():
        raise AppError("INVALID_SLUG_FORMAT", "Slug must be lowercase.", 422)

    # Slug unique kontrolü
    existing = await db.execute(
        select(Organization).where(Organization.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise ConflictError("SLUG_ALREADY_EXISTS", "This slug is already taken.")

    # Org oluştur
    org = Organization(
        name=body.name,
        slug=body.slug,
        plan="free",
        is_active=True,
        created_by=current_user.user_id,
    )
    db.add(org)
    await db.flush()

    # Owner üyeliği otomatik ekle
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.user_id,
        role="owner",
    )
    db.add(membership)
    await db.commit()

    return success({
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "role": "owner",
        "created_at": org.created_at.isoformat(),
    })


# ─── GET /organizations/{org_id} ─────────────────────────

@router.get("/{org_id}")
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Org bilgisi — minimum member rolü gerekli."""
    # Org token'daki org ile eşleşmeli
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    org = await db.get(Organization, org_id)
    if not org or not org.is_active:
        raise NotFoundError("ORGANIZATION_NOT_FOUND", "Organization not found.")

    # Member sayısı
    count_result = await db.execute(
        select(func.count()).where(OrganizationMember.organization_id == org_id)
    )
    member_count = count_result.scalar() or 0

    return success({
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "member_count": member_count,
        "created_at": org.created_at.isoformat(),
    })


# ─── PATCH /organizations/{org_id} ───────────────────────

@router.patch("/{org_id}")
async def update_organization(
    org_id: uuid.UUID,
    body: UpdateOrgRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    """Org adını güncelle. Slug ve ID değiştirilemez."""
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    org = await db.get(Organization, org_id)
    if not org or not org.is_active:
        raise NotFoundError("ORGANIZATION_NOT_FOUND", "Organization not found.")

    org.name = body.name
    org.updated_at = datetime.now(UTC)
    await db.commit()

    return success({
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "updated_at": org.updated_at.isoformat(),
    })


# ─── DELETE /organizations/{org_id} ──────────────────────

@router.delete("/{org_id}", status_code=204)
async def delete_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("owner")),
):
    """
    Org'u hard delete ile siler. Geri alınamaz.
    Spec: tüm üyelikleri ve davetler CASCADE ile silinir.
    Aktif token'lar max 15 dakika içinde expire olur.
    """
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    org = await db.get(Organization, org_id)
    if not org:
        raise NotFoundError("ORGANIZATION_NOT_FOUND", "Organization not found.")

    await db.delete(org)
    await db.commit()
    # 204 — body yok


# ─── GET /organizations/{org_id}/members ─────────────────

@router.get("/{org_id}/members")
async def list_members(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Org üye listesi — minimum member rolü."""
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
        .options(selectinload(OrganizationMember.user))
    )
    memberships = result.scalars().all()

    return success([
        {
            "user_id": str(m.user_id),
            "email": m.user.email,
            "full_name": m.user.full_name,
            "role": m.role,
            "joined_at": m.joined_at.isoformat(),
        }
        for m in memberships
    ])


# ─── PATCH /organizations/{org_id}/members/{user_id} ─────

@router.patch("/{org_id}/members/{target_user_id}")
async def update_member_role(
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("owner")),
):
    """
    Üye rolünü değiştir. Spec hataları:
    - CANNOT_CHANGE_OWNER_ROLE: hedef kullanıcı owner
    - CANNOT_CHANGE_OWN_ROLE: kendi rolünü değiştiremez
    """
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    # Kendi rolünü değiştiremez
    if target_user_id == ctx.user_id:
        raise AppError("CANNOT_CHANGE_OWN_ROLE", "You cannot change your own role.", 422)

    result = await db.execute(
        select(OrganizationMember)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == target_user_id,
        )
        .options(selectinload(OrganizationMember.user))
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise NotFoundError("NOT_A_MEMBER", "User is not a member of this organization.")

    # Owner rolü değiştirilemez
    if membership.role == "owner":
        raise AppError("CANNOT_CHANGE_OWNER_ROLE", "Owner role cannot be changed.", 422)

    membership.role = body.role
    await db.commit()

    return success({
        "user_id": str(membership.user_id),
        "email": membership.user.email,
        "role": membership.role,
        "updated_at": datetime.now(UTC).isoformat(),
    })


# ─── DELETE /organizations/{org_id}/members/{user_id} ────

@router.delete("/{org_id}/members/{target_user_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("owner")),
):
    """
    Üyeyi org'dan çıkar. Owner kendini çıkaramaz.
    Spec: token max 15 dk daha geçerli (trade-off).
    """
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    if target_user_id == ctx.user_id:
        raise AppError("CANNOT_REMOVE_OWNER", "Owner cannot remove themselves from the organization.", 422)

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == target_user_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise NotFoundError("NOT_A_MEMBER", "User is not a member of this organization.")

    await db.delete(membership)
    await db.commit()
    # 204 — body yok


# ─── POST /organizations/{org_id}/invitations ────────────

@router.post("/{org_id}/invitations", status_code=201)
async def create_invitation(
    org_id: uuid.UUID,
    body: CreateInvitationRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("owner")),
):
    """
    Davet gönder. Spec hataları:
    - ALREADY_MEMBER: kullanıcı zaten üye
    - INVITATION_ALREADY_PENDING: aynı email'e bekleyen davet var
    - CANNOT_INVITE_OWNER: owner rolüyle davet edilemez
    """
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    # Owner rolüyle davet edilemez (schema'da da kontrol var, çift güvence)
    if body.role == "owner":
        raise AppError("CANNOT_INVITE_OWNER", "Cannot invite with owner role.", 422)

    # Kullanıcı zaten üye mi?
    invited_user = await db.execute(
        select(User).where(User.email == body.email)
    )
    invited_user = invited_user.scalar_one_or_none()

    if invited_user:
        existing_membership = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == invited_user.id,
            )
        )
        if existing_membership.scalar_one_or_none():
            raise ConflictError("ALREADY_MEMBER", "This user is already a member of the organization.")

    # Bekleyen davet var mı?
    pending = await db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == org_id,
            OrganizationInvitation.email == body.email,
            OrganizationInvitation.status == "pending",
        )
    )
    if pending.scalar_one_or_none():
        raise ConflictError("INVITATION_ALREADY_PENDING", "A pending invitation already exists for this email.")

    # Token üret
    raw_token = jwt_service.generate_secure_token()
    token_hash = jwt_service.hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=7)

    invitation = OrganizationInvitation(
        organization_id=org_id,
        invited_by=ctx.user_id,
        email=body.email,
        role=body.role,
        token_hash=token_hash,
        status="pending",
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()
    await db.commit()

    # Redis'e yaz
    await store_invite_token(redis, token_hash, str(invitation.id))

    # Org bilgisini getir
    org = await db.get(Organization, org_id)
    inviter_result = await db.execute(select(User).where(User.id == ctx.user_id))
    inviter = inviter_result.scalar_one_or_none()
    inviter_name = inviter.full_name or inviter.email if inviter else ctx.email

    # Email gönder
    await send_invitation_email(
        email=body.email,
        org_name=org.name if org else "Unknown",
        invited_by=inviter_name,
        raw_token=raw_token,
        role=body.role,
    )

    return success({
        "id": str(invitation.id),
        "email": invitation.email,
        "role": invitation.role,
        "expires_at": invitation.expires_at.isoformat(),
    })


# ─── DELETE /organizations/{org_id}/invitations/{inv_id} ─

@router.delete("/{org_id}/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(
    org_id: uuid.UUID,
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("owner")),
):
    """Bekleyen daveti iptal et. Sadece pending davetler iptal edilebilir."""
    if ctx.org_id != org_id:
        raise ForbiddenError("INSUFFICIENT_PERMISSIONS", "Access denied to this organization.")

    result = await db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == org_id,
        )
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise NotFoundError("INVITATION_NOT_FOUND", "Invitation not found.")

    if invitation.status != "pending":
        raise ConflictError("INVITATION_NOT_CANCELLABLE", "Only pending invitations can be cancelled.")

    invitation.status = "cancelled"
    await revoke_invite_token(redis, invitation.token_hash)
    await db.commit()
    # 204 — body yok

