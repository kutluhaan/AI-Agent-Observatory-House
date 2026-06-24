"""team shared file system

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-25

Ekibe özel ORTAK dosya sistemi (E). agent_files'ın ekip karşılığı; bir ekipteki tüm
üyeler aynı alanı paylaşır. Bir agent yazınca diğerleri ve kullanıcı görür/indirir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("path", sa.String(1000), nullable=False),
        sa.Column("is_dir", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("team_id", "path", name="uq_team_file_path"),
    )


def downgrade() -> None:
    op.drop_table("team_files")
