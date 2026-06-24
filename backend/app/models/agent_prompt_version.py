"""Agent prompt sürümleri — loop it.6 (prompt versiyonlama)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# agent.update'te snapshot alınan config alanları (name/description versiyonlanmaz)
VERSIONED_FIELDS = ("system_prompt", "provider", "model", "temperature", "max_tokens", "tool_names", "hitl_tool_names")


class AgentPromptVersion(Base):
    """Bir agent config'inin tam snapshot'ı (system_prompt + model + tool'lar + temperature)."""
    __tablename__ = "agent_prompt_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_prompt_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7, server_default="0.7")
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_names: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    hitl_tool_names: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
