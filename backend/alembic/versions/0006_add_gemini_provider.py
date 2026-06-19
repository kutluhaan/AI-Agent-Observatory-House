"""add gemini to provider check constraint

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-19

provider_credentials.ck_provider_name CHECK'ine 'gemini' eklenir (M7 Gemini provider).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_provider_name", "provider_credentials", type_="check")
    op.create_check_constraint(
        "ck_provider_name",
        "provider_credentials",
        "provider IN ('openai', 'anthropic', 'gemini', 'ollama')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_provider_name", "provider_credentials", type_="check")
    op.create_check_constraint(
        "ck_provider_name",
        "provider_credentials",
        "provider IN ('openai', 'anthropic', 'ollama')",
    )
