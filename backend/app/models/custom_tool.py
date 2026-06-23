"""Kullanıcı tanımlı HTTP tool'ları (org seviyesinde) — B1 (#1)."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class CustomTool(Base):
    """
    Org bazlı, kullanıcı tanımlı HTTP tool. Agent'lar bunu çağırabilir:
    LLM `parameters` şemasına göre argüman üretir → URL placeholder + gövde/sorgu
    olarak gönderilir → yanıt metni döner.

    headers: Fernet ile şifreli JSON (gizli anahtarlar içerebilir); yanıtta ham dönmez.
    """
    __tablename__ = "custom_tools"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_custom_tool_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)         # tool adı (LLM'e görünür)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")  # GET|POST|PUT|PATCH|DELETE
    url: Mapped[str] = mapped_column(String(1000), nullable=False)        # {param} placeholder olabilir
    encrypted_headers: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet JSON
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # JSON Schema (object)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization")
