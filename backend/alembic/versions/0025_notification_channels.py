"""notification channels (messaging)

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-24

D/#loop it.4 — Mesajlaşma & Bildirim kategorisi.
Org-bazlı bildirim kanalı: bir generic webhook URL'i (Slack/Discord/Teams incoming
webhook'ları dahil) ŞİFRELİ saklanır; send_notification tool'u buradan okur.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("channel_type", sa.String(30), nullable=False, server_default="webhook"),
        sa.Column("encrypted_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_notify_name"),
    )


def downgrade() -> None:
    op.drop_table("notification_channels")
