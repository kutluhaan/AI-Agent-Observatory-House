"""drop workflow tables
Revision ID: 0034
Revises: 0033
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("workflow_node_results")
    op.drop_table("workflow_runs")
    op.drop_table("workflows")


def downgrade() -> None:
    pass
