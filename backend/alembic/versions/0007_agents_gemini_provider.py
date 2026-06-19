"""add gemini to agents provider check constraint

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-19

agents.ck_agents_provider CHECK'ine 'gemini' eklenir. (0006 provider_credentials'ı
güncellemişti ama agents tablosundaki ayrı constraint kaçırılmıştı.)
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_agents_provider", "agents", type_="check")
    op.create_check_constraint(
        "ck_agents_provider",
        "agents",
        "provider IN ('openai', 'anthropic', 'gemini', 'ollama')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agents_provider", "agents", type_="check")
    op.create_check_constraint(
        "ck_agents_provider",
        "agents",
        "provider IN ('openai', 'anthropic', 'ollama')",
    )
