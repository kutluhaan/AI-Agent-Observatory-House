"""conversations + conversation_messages

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-20

Kalıcı sohbet thread'leri (Faz 1). Conversation kullanıcıya özel (user_id),
org+agent-scoped. Mesajlar CASCADE.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="New chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_conversations_org", "conversations", ["organization_id"])
    op.create_index("idx_conversations_agent", "conversations", ["agent_id"])
    op.create_index("idx_conversations_user", "conversations", ["user_id"])
    op.create_index("idx_conversations_last_message", "conversations", ["last_message_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("segments", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_conv_message_role"),
    )
    op.create_index("idx_conv_messages_conv", "conversation_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
