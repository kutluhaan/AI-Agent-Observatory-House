"""Ekip Knowledge Base — agent knowledge'ın ekip karşılığı (B2)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TEAM_KNOWLEDGE_KINDS = ("constitution", "rule", "instruction", "prompt")  # hepsi her zaman aktif


class TeamKnowledge(Base):
    """
    Ekip-seviye bilgi öğesi. Aktif öğeler TÜM ekip üyelerinin system prompt'una
    eklenir (build_member_runner). Ekibin ortak anayasası/kuralları/talimatları.
    """
    __tablename__ = "team_knowledge"
    __table_args__ = (
        CheckConstraint("kind IN ('constitution', 'rule', 'instruction', 'prompt')", name="ck_team_knowledge_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
