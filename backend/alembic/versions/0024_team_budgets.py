"""team budgets + shared instructions

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-24

B3+: Ekip-seviye limitler (sektör pratiği — Anthropic multi-agent + loop control):
  teams.shared_instructions  — tüm üyelere eklenen ekip promptu (ortak bağlam + kurallar)
  teams.max_delegations      — bir run'da Coordinator'ın yapabileceği max delege (iletişim bütçesi)
  teams.run_timeout_seconds  — tüm ekip çalıştırması için üst süre sınırı (Coordinator)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("shared_instructions", sa.Text(), nullable=True))
    op.add_column("teams", sa.Column("max_delegations", sa.Integer(), nullable=False, server_default="12"))
    op.add_column("teams", sa.Column("run_timeout_seconds", sa.Integer(), nullable=False, server_default="600"))


def downgrade() -> None:
    op.drop_column("teams", "run_timeout_seconds")
    op.drop_column("teams", "max_delegations")
    op.drop_column("teams", "shared_instructions")
