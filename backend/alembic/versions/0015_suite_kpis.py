"""suite-level selectable KPIs

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-23

F4.2: test_suites'e `kpis` (JSONB, nullable) kolonu ekler — kullanıcının o suite
için izlemeyi seçtiği metrik anahtarları (ör. ["success_run_rate", "avg_latency_ms"]).
NULL = varsayılan KPI seti kullanılır (kpi_catalog.DEFAULT_KPIS).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_suites",
        sa.Column("kpis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test_suites", "kpis")
