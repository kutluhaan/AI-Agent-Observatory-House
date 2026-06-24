"""database connections (sql tools)

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-24

loop it.8 — Veritabanı & SQL kategorisi. Org-bazlı, ŞİFRELİ DSN ile dış PostgreSQL
bağlantısı. sql_query/sql_schema/sql_sample tool'ları buradan okur (SALT-OKUNUR).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "db_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("db_type", sa.String(30), nullable=False, server_default="postgres"),
        sa.Column("encrypted_dsn", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_dbconn_name"),
    )


def downgrade() -> None:
    op.drop_table("db_connections")
