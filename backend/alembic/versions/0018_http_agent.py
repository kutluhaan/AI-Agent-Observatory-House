"""http (external OpenAI-compatible) agent provider

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-23

F7.1: Dış (self-hosted) OpenAI-uyumlu agent endpoint'i.
  agents.endpoint_url      — per-agent OpenAI-uyumlu kök (ör. http://host:8000/v1)
  agents.endpoint_api_key  — Fernet ile şifreli (opsiyonel)
  ck_agents_provider'a 'http' eklenir.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITH_HTTP = "provider IN ('openai', 'anthropic', 'gemini', 'ollama', 'custom', 'http')"
_WITHOUT = "provider IN ('openai', 'anthropic', 'gemini', 'ollama', 'custom')"


def upgrade() -> None:
    op.add_column("agents", sa.Column("endpoint_url", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("endpoint_api_key", sa.Text(), nullable=True))
    op.drop_constraint("ck_agents_provider", "agents", type_="check")
    op.create_check_constraint("ck_agents_provider", "agents", _WITH_HTTP)


def downgrade() -> None:
    op.drop_constraint("ck_agents_provider", "agents", type_="check")
    op.create_check_constraint("ck_agents_provider", "agents", _WITHOUT)
    op.drop_column("agents", "endpoint_api_key")
    op.drop_column("agents", "endpoint_url")
