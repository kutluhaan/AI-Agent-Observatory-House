"""Veritabanı bağlantıları (SQL tool'ları) — loop it.8."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class DbConnection(Base):
    """
    Org-bazlı dış veritabanı bağlantısı. DSN (postgresql://user:pass@host/db) Fernet ile
    şifreli; ham hâli API'de dönmez. sql_query/sql_schema/sql_sample tool'ları SALT-OKUNUR
    (readonly transaction) sorgular için kullanır.
    """
    __tablename__ = "db_connections"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_dbconn_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    db_type: Mapped[str] = mapped_column(String(30), nullable=False, default="postgres", server_default="postgres")
    encrypted_dsn: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization")
