"""provider credentials

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17

provider_credentials tablosu — org bazlı LLM provider key yönetimi (M7)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name="fk_provider_credentials_org_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organization_id", "provider", name="uq_org_provider"),
        sa.CheckConstraint("provider IN ('openai', 'anthropic', 'ollama')", name="ck_provider_name"),
    )
    op.create_index("idx_provider_credentials_org_id", "provider_credentials", ["organization_id"])


def downgrade() -> None:
    op.drop_table("provider_credentials")
