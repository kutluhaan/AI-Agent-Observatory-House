import os
import subprocess

import pytest
from sqlalchemy import create_engine, text

EXPECTED_TABLES = {
    "users",
    "organizations",
    "organization_members",
    "refresh_tokens",
    "email_verifications",
    "password_resets",
    "organization_invitations",
    "oauth_accounts",
}


def _sync_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url.replace("postgresql+asyncpg", "postgresql+psycopg")


@pytest.mark.integration
def test_alembic_upgrade_head():
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.integration
def test_all_auth_tables_exist():
    engine = create_engine(_sync_database_url())
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                  AND table_name = ANY(:names)
                """
            ),
            {"names": list(EXPECTED_TABLES)},
        ).fetchall()
    assert {r[0] for r in rows} == EXPECTED_TABLES


@pytest.mark.integration
def test_alembic_at_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()

    engine = create_engine(_sync_database_url())
    with engine.connect() as conn:
        version = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert version == head


@pytest.mark.integration
def test_pending_invitation_partial_unique_index():
    engine = create_engine(_sync_database_url())
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT i.indisunique, pg_get_expr(i.indpred, i.indrelid)
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                WHERE c.relname = 'uq_org_invitation_pending_email'
                """
            )
        ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] is not None and "pending" in row[1]