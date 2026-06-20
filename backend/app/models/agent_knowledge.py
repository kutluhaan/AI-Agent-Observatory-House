"""
AgentKnowledge — agent'ın yeteneklerini/davranışını şekillendiren bilgi öğeleri (Faz 4).

kind:
  constitution / rule / instruction / prompt  → her zaman aktif: system prompt'a enjekte edilir
  skill                                        → talep üzerine: list_skills/read_skill tool'larıyla okunur

Her satır tek bir öğe (ör. birden çok "rule" = birden çok satır). Agent başına izole.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

KNOWLEDGE_KINDS = ("constitution", "rule", "instruction", "prompt", "skill")
ALWAYS_ON_KINDS = ("constitution", "rule", "instruction", "prompt")


class AgentKnowledge(Base):
    __tablename__ = "agent_knowledge"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('constitution', 'rule', 'instruction', 'prompt', 'skill')",
            name="ck_agent_knowledge_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AgentKnowledge agent={self.agent_id} {self.kind}={self.name!r}>"
