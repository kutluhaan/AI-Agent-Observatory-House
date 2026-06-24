"""agent prompt versions

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-24

loop it.6 — Prompt versiyonlama. Agent config'inin (system_prompt + model + tool'lar +
temperature) tam snapshot'ı. agent her güncellenince eski hal sürüm olur; rollback =
bir sürümü geri yükle. agents.prompt_version = aktif sürüm no.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("prompt_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "agent_prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("tool_names", JSONB(), nullable=False, server_default="[]"),
        sa.Column("hitl_tool_names", JSONB(), nullable=False, server_default="[]"),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_prompt_version"),
    )


def downgrade() -> None:
    op.drop_table("agent_prompt_versions")
    op.drop_column("agents", "prompt_version")
