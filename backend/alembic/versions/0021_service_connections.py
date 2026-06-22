"""service connections (user OAuth, Gmail)

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-23

G1: Kullanıcı OAuth bağlantıları (Gmail vb.). Token'lar Fernet ile şifreli.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "service_connections",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("account_email", sa.String(length=320), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "organization_id", "provider", name="uq_user_org_provider_conn"),
    )


def downgrade() -> None:
    op.drop_table("service_connections")
