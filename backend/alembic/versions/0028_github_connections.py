"""github connections (github tools)

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-24

loop it.9 — GitHub kategorisi. Org-bazlı, ŞİFRELİ Personal Access Token.
github_search/repo_info/issues/read_file tool'ları buradan okur.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_github_name"),
    )


def downgrade() -> None:
    op.drop_table("github_connections")
