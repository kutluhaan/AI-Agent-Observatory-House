import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, CheckConstraint, func, text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.organization import Organization


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # idx_refresh_tokens_user_id — toplu revoke (password reset)
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,  # idx_refresh_tokens_token_hash — token lookup
        # SHA-256 hash — raw token hiçbir zaman DB'de saklanmaz
    )
    device_info: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        # User-Agent string — Faz 2 session listesi için
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        # Faz 5 security auditing için
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Oluşturulma + 7 gün
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        # TRUE → REFRESH_TOKEN_REVOKED — logout veya password reset'te set edilir
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # is_revoked=TRUE yapılırken set edilir — audit için
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.is_revoked}>"


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        # SHA-256 — /auth/verify-email'de gelen token hash'lenip karşılaştırılır
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Oluşturulma + 24 saat
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # NULL = henüz kullanılmadı
        # NULL değilse token tüketilmiş — single-use enforcement
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="email_verifications")

    def __repr__(self) -> str:
        return f"<EmailVerification user={self.user_id} used={self.used_at is not None}>"


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # idx_password_resets_user_id — önceki token'ları geçersiz kılma
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,  # idx_password_resets_token_hash — reset lookup
        # SHA-256 — /auth/reset-password'da Redis fast path + DB check
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Oluşturulma + 30 dakika (kısa TTL — hassas işlem)
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # NULL = kullanılmadı
        # Single-use enforcement + önceki token'ları geçersiz kılmak için
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="password_resets")

    def __repr__(self) -> str:
        return f"<PasswordReset user={self.user_id} used={self.used_at is not None}>"


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        Index(
            "uq_org_invitation_pending_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_invitation_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'cancelled')",
            name="ck_invitation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),  # RESTRICT — daveti gönderen silinemez
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,  # idx_invitations_email — pending davet kontrolü
        # Kabul akışında giriş yapan kullanıcının email'i ile karşılaştırılır (EMAIL_MISMATCH)
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # admin | member — owner rolüyle davet gönderilemez (CANNOT_INVITE_OWNER)
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,  # idx_invitations_token_hash — davet kabul akışı
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        # pending | accepted | expired | cancelled
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Oluşturulma + 7 gün
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # Davet kabul edildiğinde set edilir
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="invitations"
    )

    def __repr__(self) -> str:
        return f"<OrganizationInvitation email={self.email} status={self.status}>"


class OAuthAccount(Base):
    """Faz 4 için hazır — şimdi tablo oluşturulur, implementasyon sonra."""
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_id",
            name="uq_oauth_provider_id",
            # Aynı Google hesabı iki farklı kullanıcıya bağlanamaz
        ),
        CheckConstraint(
            "provider IN ('google', 'github')",
            name="ck_oauth_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # google | github — CHECK constraint migration'da
    )
    provider_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        # Provider'ın user ID'si — OAuth callback'inde gelen ID ile eşleştirme
    )
    access_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        # AES-256 ile şifreli — Faz 4'te implement edilecek
    )
    refresh_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        # AES-256 ile şifreli — Faz 4'te implement edilecek
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    def __repr__(self) -> str:
        return f"<OAuthAccount provider={self.provider} user={self.user_id}>"
