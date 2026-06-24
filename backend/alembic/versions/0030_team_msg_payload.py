"""team run message payload (tool args)

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-25

İşbirliği akışı UI: tool mesajlarına argüman/özet (web_search sorgusu, write_todos
maddeleri) saklamak için payload alanı. UI bunu checkbox / 'sadece aranan site' gösterir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("team_run_messages", sa.Column("payload", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("team_run_messages", "payload")
