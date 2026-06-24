"""Bildirim akışı girdileri (sent log + sistem olayları) — D."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class Notification(Base):
    """
    Navbar 'Bildirimler' feed girdisi. kind='sent' (agent send_notification ile gönderdi)
    veya 'system' (ekip run bitti/hata, test bitti). NotificationChannel (webhook config)
    ile karıştırma — bu in-app feed kaydıdır.
    """
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # sent | system
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="info", server_default="info")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    organization: Mapped["Organization"] = relationship("Organization")
