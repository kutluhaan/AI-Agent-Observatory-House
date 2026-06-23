"""team chat conversations

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-23

B3 (#3): Ekiple çok-turlu sohbet. team_runs.conversation_id ile run'lar bir
sohbete gruplanır; Coordinator önceki turları hatırlar.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("team_runs", sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_team_runs_conversation_id", "team_runs", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_team_runs_conversation_id", table_name="team_runs")
    op.drop_column("team_runs", "conversation_id")
