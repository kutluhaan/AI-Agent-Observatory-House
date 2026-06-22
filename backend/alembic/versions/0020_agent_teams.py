"""agent teams (multi-agent collaboration)

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-23

F8: Agent ekipleri. teams + team_members (agent+rol) + team_runs + team_run_messages
(delegasyon + paylaşılan pano timeline'ı, kalıcı).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_team_name"),
    )
    op.create_table(
        "team_members",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("team_id", _UUID, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_id", _UUID, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("role_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "team_runs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("team_id", _UUID, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("input", sa.Text(), nullable=False),
        sa.Column("final_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "team_run_messages",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("team_run_id", _UUID, sa.ForeignKey("team_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("from_role", sa.String(length=50), nullable=True),
        sa.Column("to_role", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("team_run_messages")
    op.drop_table("team_runs")
    op.drop_table("team_members")
    op.drop_table("teams")
