"""C1 — make_tool_recorder: üye tool çağrılarını timeline'a yazar, team tool'ları atlar."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.team.executor import make_tool_recorder


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_records_normal_tool():
    db = _db()
    rec = make_tool_recorder(db, uuid.uuid4(), "researcher")
    await rec("web_search", {"q": "x"}, "3 sonuç bulundu")
    assert db.add.call_count == 1
    msg = db.add.call_args.args[0]
    assert msg.kind == "tool"
    assert msg.from_role == "researcher"
    assert msg.title == "web_search"


@pytest.mark.asyncio
async def test_skips_team_tools():
    db = _db()
    rec = make_tool_recorder(db, uuid.uuid4(), "coordinator")
    for t in ("delegate", "team_share", "team_board"):
        await rec(t, {}, "ok")
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_truncates_long_output():
    db = _db()
    rec = make_tool_recorder(db, uuid.uuid4(), "worker")
    await rec("read_url", {}, "x" * 1000)
    msg = db.add.call_args.args[0]
    assert len(msg.content) <= 401 and msg.content.endswith("…")
