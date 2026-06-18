"""agent schema

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-18
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, nullable=True),
        sa.Column("max_steps", sa.Integer, nullable=False, server_default="10"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="120"),
        sa.Column(
            "tool_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])
    op.create_unique_constraint("uq_org_agent_name", "agents", ["organization_id", "name"])

    # provider değeri kontrol kısıtı
    op.create_check_constraint(
        "ck_agents_provider",
        "agents",
        "provider IN ('openai', 'anthropic', 'ollama')",
    )

    # updated_at otomatik güncelleme trigger'ı (0001'deki trigger fonksiyonunu yeniden kullanır)
    op.execute("""
        CREATE TRIGGER trg_agents_updated_at
        BEFORE UPDATE ON agents
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_agents_updated_at ON agents")
    op.drop_table("agents")
