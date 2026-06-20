"""
AgentFile — agent'ın izole sanal dosya sistemi (Faz 3).

Her satır bir dosya veya klasör (is_dir). path agent içinde benzersiz, örn.
"notes/research.md". Klasörler mkdir ile açıkça oluşturulur (boş klasör için);
dosya yollarındaki üst klasörler UI'da implicit olarak da gösterilir.

İzolasyon: agent_id'ye bağlı — bir agent diğerinin dosyalarına erişemez.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

if TYPE_CHECKING:
    pass


class AgentFile(Base):
    __tablename__ = "agent_files"
    __table_args__ = (
        UniqueConstraint("agent_id", "path", name="uq_agent_file_path"),
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
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_dir: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        kind = "dir" if self.is_dir else "file"
        return f"<AgentFile agent={self.agent_id} {kind}={self.path!r}>"
