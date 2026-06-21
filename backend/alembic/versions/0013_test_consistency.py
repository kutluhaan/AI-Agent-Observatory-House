"""test consistency (repeat runs)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-21

Faz C: test_cases'e repeat (N tekrar) + min_pass_rate; test_case_results'e
consistency (tekrar istatistikleri) eklenir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column("repeat", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "test_cases",
        sa.Column("min_pass_rate", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "test_case_results",
        sa.Column("consistency", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test_case_results", "consistency")
    op.drop_column("test_cases", "min_pass_rate")
    op.drop_column("test_cases", "repeat")
