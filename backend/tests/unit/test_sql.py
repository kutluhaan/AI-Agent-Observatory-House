"""loop it.8 — SQL tool'ları: salt-okunur doğrulama (DB'siz testlenebilir)."""
import uuid

import pytest

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.tools.sql import register_sql_tools

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reg():
    register_sql_tools()


async def _q(query):
    ctx = ToolContext(org_id=uuid.uuid4(), trace_id="t", db=None, redis=None)
    return await ToolRegistry.get("sql_query").handler(ctx, query=query)


@pytest.mark.asyncio
async def test_rejects_writes():
    for bad in ("DELETE FROM users", "UPDATE x SET y=1", "DROP TABLE x", "INSERT INTO x VALUES (1)"):
        assert "error" in await _q(bad)


@pytest.mark.asyncio
async def test_rejects_multi_statement():
    assert "error" in await _q("SELECT 1; DROP TABLE x")


@pytest.mark.asyncio
async def test_valid_select_passes_validation():
    # geçerli SELECT → validation geçer, sonra 'no db context' (db=None)
    assert "no db context" in await _q("SELECT 1")
    assert "no db context" in await _q("WITH t AS (SELECT 1) SELECT * FROM t")


@pytest.mark.asyncio
async def test_sample_rejects_bad_table():
    ctx = ToolContext(org_id=uuid.uuid4(), trace_id="t", db=object(), redis=None)
    out = await ToolRegistry.get("sql_sample").handler(ctx, table="x; DROP TABLE y")
    assert "error" in out
