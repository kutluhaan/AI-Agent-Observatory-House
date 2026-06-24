"""Bildirim kanalları (Mesajlaşma) — loop it.4."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class NotificationChannel(Base):
    """
    Org-bazlı bildirim kanalı — bir generic webhook URL'i (Slack/Discord/Teams
    incoming webhook'ları dahil). URL Fernet ile şifreli; ham hâli API'de dönmez.
    `send_notification` tool'u kanalı ada göre bulur, çözer ve JSON POST eder.
    """
    __tablename__ = "notification_channels"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_notify_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False, default="webhook", server_default="webhook")
    encrypted_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization")
