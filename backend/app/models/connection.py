"""Kullanıcı servis bağlantıları (OAuth) — G1 (Gmail vb.)."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ServiceConnection(Base):
    """
    Bir kullanıcının bir dış servise (ör. Google/Gmail) OAuth bağlantısı.

    Token'lar Fernet ile şifreli. Kapsam: (user, org, provider) benzersiz —
    kullanıcı her org için ayrı bağlar (multi-tenant izolasyon).
    """
    __tablename__ = "service_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", "provider", name="uq_user_org_provider_conn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google
    account_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)  # boşlukla ayrık
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
