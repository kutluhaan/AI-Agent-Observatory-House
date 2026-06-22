"""A/B prompt experiments on test_runs

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-23

F4.3: test_runs'a A/B karşılaştırması için üç kolon ekler:
  experiment_id          — aynı A/B denemesindeki varyant run'larını gruplar (nullable, indexli)
  variant_label          — varyant adı (ör. "Kısa prompt")
  system_prompt_override — bu run için agent'ın system prompt'unu geçici ezme

NULL experiment_id = normal tekil run (A/B değil). Override agent'ı kalıcı bozmaz;
yalnızca o run'ın çalıştırılmasında kullanılır.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("experiment_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("test_runs", sa.Column("variant_label", sa.String(length=120), nullable=True))
    op.add_column("test_runs", sa.Column("system_prompt_override", sa.Text(), nullable=True))
    op.create_index("ix_test_runs_experiment_id", "test_runs", ["experiment_id"])


def downgrade() -> None:
    op.drop_index("ix_test_runs_experiment_id", table_name="test_runs")
    op.drop_column("test_runs", "system_prompt_override")
    op.drop_column("test_runs", "variant_label")
    op.drop_column("test_runs", "experiment_id")
