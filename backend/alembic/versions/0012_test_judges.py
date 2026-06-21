"""test judges (LLM-as-judge)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-21

Faz B: test_cases'e judge tanımları (judges), test_case_results'e judge skorları
(judge_results) eklenir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column(
            "judges",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "test_case_results",
        sa.Column("judge_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test_case_results", "judge_results")
    op.drop_column("test_cases", "judges")
