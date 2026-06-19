"""
Invitations Router — M5

POST /invitations/{token}/accept — Davet kabul et

Bu endpoint /organizations prefix'i dışında çünkü:
- Davet edilen kişi org_id'yi bilmeden linke tıklıyor
- URL: /invitations/{token}/accept
"""
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.responses import AppError, ConflictError, ForbiddenError, success
from app.models.auth import OrganizationInvitation
from app.models.organization import OrganizationMember
from app.models.user import User
from app.services import jwt_service
from app.services.token_store import get_invite_id, revoke_invite_token

router = APIRouter()


@router.get("/{token}")
async def get_invitation_preview(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Davet önizlemesi — auth gerektirmez (token zaten gizli anahtar).
    Kabul akışından ÖNCE kullanıcıya org/rol/davet eden bilgisini gösterir.
    Token'ı tüketmez.
    """
    token_hash = jwt_service.hash_token(token)

    result = await db.execute(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_hash == token_hash)
        .options(selectinload(OrganizationInvitation.organization))
    )
    invitation = result.scalar_one_or_none()

    if not invitation or invitation.status != "pending":
        raise AppError("INVITATION_EXPIRED", "Invitation has expired or is invalid.", 410)

    expires_at = (
        invitation.expires_at.replace(tzinfo=UTC)
        if invitation.expires_at.tzinfo is None
        else invitation.expires_at
    )
    if expires_at < datetime.now(UTC):
        raise AppError("INVITATION_EXPIRED", "This invitation has expired.", 410)

    inviter_result = await db.execute(select(User).where(User.id == invitation.invited_by))
    inviter = inviter_result.scalar_one_or_none()
    inviter_name = (inviter.full_name or inviter.email) if inviter else "A teammate"

    return success({
        "org_name": invitation.organization.name,
        "org_slug": invitation.organization.slug,
        "invited_by": inviter_name,
        "role": invitation.role,
        "email": invitation.email,
    })


@router.post("/{token}/accept")
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Davet kabul et.

    Spec edge case'leri:
    - EMAIL_MISMATCH: giriş yapan email != davet edilen email
    - INVITATION_EXPIRED: 7 gün dolmuş veya token geçersiz
    - INVITATION_ALREADY_USED: daha önce kabul edilmiş / iptal edilmiş
    - ALREADY_MEMBER: kullanıcı zaten bu org'un üyesi
    """
    token_hash = jwt_service.hash_token(token)

    # Redis fast-path — token Redis'te yoksa ya expired ya da geçersiz
    invitation_id_str = await get_invite_id(redis, token_hash)
    if not invitation_id_str:
        raise AppError("INVITATION_EXPIRED", "Invitation has expired or is invalid.", 410)

    # DB'den getir
    result = await db.execute(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_hash == token_hash)
        .options(selectinload(OrganizationInvitation.organization))
    )
    invitation = result.scalar_one_or_none()

    if not invitation:
        raise AppError("INVITATION_EXPIRED", "Invitation has expired or is invalid.", 410)

    # Status kontrolü
    if invitation.status != "pending":
        raise ConflictError("INVITATION_ALREADY_USED", "This invitation has already been used or cancelled.")

    # TTL kontrolü
    expires_at = invitation.expires_at.replace(tzinfo=UTC) if invitation.expires_at.tzinfo is None else invitation.expires_at
    if expires_at < datetime.now(UTC):
        invitation.status = "expired"
        await db.commit()
        await revoke_invite_token(redis, token_hash)
        raise AppError("INVITATION_EXPIRED", "This invitation has expired.", 410)

    # Spec: giriş yapan email == davet edilen email (EMAIL_MISMATCH koruması)
    user_result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = user_result.scalar_one_or_none()

    if not user or user.email != invitation.email:
        raise ForbiddenError(
            "EMAIL_MISMATCH",
            "The invitation was sent to a different email address. Please log in with the invited email.",
        )

    # Zaten üye mi?
    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == current_user.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError("ALREADY_MEMBER", "You are already a member of this organization.")

    # Üyelik oluştur
    membership = OrganizationMember(
        organization_id=invitation.organization_id,
        user_id=current_user.user_id,
        role=invitation.role,
    )
    db.add(membership)

    # Daveti tüket
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(UTC)
    await db.commit()

    # Redis'ten temizle
    await revoke_invite_token(redis, token_hash)

    return success({
        "organization": {
            "id": str(invitation.organization.id),
            "name": invitation.organization.name,
            "slug": invitation.organization.slug,
        },
        "role": invitation.role,
    })
