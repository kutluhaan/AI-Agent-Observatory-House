import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Agent(Base):
    """
    Org bazlı agent konfigürasyonu.

    tool_names: JSONB string listesi — kayıtlı tool isimlerine referans verir.
    Araçlar kodda tanımlanır; bu sütun agent'ın hangilere erişeceğini saklar.
    """
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_agent_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai | anthropic | gemini | ollama | custom | http
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    # F7.1: provider='http' — dış (self-hosted) OpenAI-uyumlu agent endpoint'i (per-agent)
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    endpoint_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet ile şifreli
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    # loop it.6: aktif prompt sürüm no (agent_prompt_versions ile)
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # ["echo", "calculator"] gibi kayıtlı tool isimlerinin listesi
    tool_names: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # HITL için insan onayı gerektiren tool isimleri (tool_names alt kümesi)
    hitl_tool_names: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # F7.2: bu agent'ın kullanabileceği MCP tool'ları [{server_id, tool_name}]
    mcp_tools: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # B1: bu agent'ın kullanabileceği org custom tool id'leri ["uuid", ...]
    custom_tool_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # İzole dosya sistemi açık mı — açıksa file tool'ları otomatik eklenir
    file_system_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Agent org={self.organization_id} name={self.name!r}>"
