"""test case result trajectory + cost

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-21

Test sonuçlarına adım-adım trajectory (JSONB) + yaklaşık maliyet (USD) ekler.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_case_results",
        sa.Column("trajectory", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "test_case_results",
        sa.Column("cost_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test_case_results", "cost_usd")
    op.drop_column("test_case_results", "trajectory")
