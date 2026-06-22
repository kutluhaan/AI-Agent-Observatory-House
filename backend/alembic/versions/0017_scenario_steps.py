"""scenario (multi-step) test cases

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-23

F6: Senaryo tabanlı testler.
  test_cases.steps              — [{input, assertions:[{type,value}]}]; NULL → tekil case
  test_case_results.steps_results — [{step, input, output, passed, latency_ms, assertions_results}]
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_cases", sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("test_case_results", sa.Column("steps_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("test_case_results", "steps_results")
    op.drop_column("test_cases", "steps")
