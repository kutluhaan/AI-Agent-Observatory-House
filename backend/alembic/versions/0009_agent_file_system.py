"""agent file system

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-20

İzole agent dosya sistemi (Faz 3): agent_files tablosu + agents.file_system_enabled.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("file_system_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "agent_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(1000), nullable=False),
        sa.Column("is_dir", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "path", name="uq_agent_file_path"),
    )
    op.create_index("idx_agent_files_agent", "agent_files", ["agent_id"])
    op.create_index("idx_agent_files_org", "agent_files", ["organization_id"])


def downgrade() -> None:
    op.drop_table("agent_files")
    op.drop_column("agents", "file_system_enabled")
