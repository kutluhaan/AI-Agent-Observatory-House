import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class ProviderCredential(Base):
    """
    Org bazlı LLM provider kimlik bilgileri.

    encrypted_key: AES-256 (Fernet) ile şifreli API key.
    Ollama için NULL olabilir — local sunucu genelde key gerektirmez.

    base_url: Ollama için zorunlu (örn: http://localhost:11434).
    OpenAI/Anthropic için NULL — SDK varsayılan endpoint'i kullanır.

    Org'un credential'ı yoksa Provider Factory .env'deki platform-level
    key'e fallback yapar (geliştirme/demo senaryosu).
    """
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_org_provider"),
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
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # openai | anthropic | ollama — CHECK constraint migration'da
    )
    encrypted_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        # Fernet ile şifreli. Ollama'da NULL olabilir.
    )
    base_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        # Ollama için zorunlu, diğerlerinde genelde NULL
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    def __repr__(self) -> str:
        return f"<ProviderCredential org={self.organization_id} provider={self.provider}>"
