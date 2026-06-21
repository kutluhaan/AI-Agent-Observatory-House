"""custom (self-hosted OpenAI-compatible) provider

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-22

F3: 'custom' provider'ı iki CHECK constraint'e ekler — provider_credentials
(ck_provider_name) ve agents (ck_agents_provider). Custom = OpenAI-uyumlu
self-hosted endpoint (base_url + opsiyonel api_key); provider_credentials.base_url
yeniden kullanılır.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WITH_CUSTOM = "provider IN ('openai', 'anthropic', 'gemini', 'ollama', 'custom')"
_WITHOUT = "provider IN ('openai', 'anthropic', 'gemini', 'ollama')"


def upgrade() -> None:
    op.drop_constraint("ck_provider_name", "provider_credentials", type_="check")
    op.create_check_constraint("ck_provider_name", "provider_credentials", _WITH_CUSTOM)
    op.drop_constraint("ck_agents_provider", "agents", type_="check")
    op.create_check_constraint("ck_agents_provider", "agents", _WITH_CUSTOM)


def downgrade() -> None:
    op.drop_constraint("ck_provider_name", "provider_credentials", type_="check")
    op.create_check_constraint("ck_provider_name", "provider_credentials", _WITHOUT)
    op.drop_constraint("ck_agents_provider", "agents", type_="check")
    op.create_check_constraint("ck_agents_provider", "agents", _WITHOUT)
