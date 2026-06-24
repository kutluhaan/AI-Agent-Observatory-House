"""notifications feed (sent log + system events)

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-25

Navbar 'Bildirimler' akışı: agent'ların gönderdiği bildirimler (sent) + sistem
olayları (system: ekip run bitti/hata, test bitti). NotificationChannel (webhook
config) ile karıştırma — bu FEED girdileridir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),       # sent | system
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),  # info|success|error
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(120), nullable=True),     # kanal adı / 'team_run' / 'test_run'
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("notifications")
