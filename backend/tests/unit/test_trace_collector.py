"""
Unit Testler — Trace Collector + WebSocket ConnectionManager (M8)

Redis için fakeredis kullanılır; ClickHouse/WebSocket'e dokunulmaz.
"""
import json
import uuid

import pytest

from app.services.trace_collector import STREAM, Tracer
from app.ws.traces import ConnectionManager


# ─── Tracer (Redis XADD) ──────────────────────────────────

@pytest.fixture
async def fake_redis():
    import fakeredis.aioredis

    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.flushall()


@pytest.mark.asyncio
async def test_tracer_emits_three_events(fake_redis):
    org_id = str(uuid.uuid4())
    tracer = Tracer(fake_redis, organization_id=org_id, name="test-run")

    await tracer.start()
    await tracer.event("llm_call_start", {"model": "gpt-4o"})
    await tracer.end(status="completed")

    assert await fake_redis.xlen(STREAM) == 3

    entries = await fake_redis.xrange(STREAM)
    events = [json.loads(fields["data"]) for _id, fields in entries]
    types = [e["type"] for e in events]
    assert types == ["agent_start", "llm_call_start", "agent_end"]
    assert all(e["organization_id"] == org_id for e in events)
    assert all(e["trace_id"] == tracer.trace_id for e in events)


@pytest.mark.asyncio
async def test_tracer_end_payload_has_status_and_times(fake_redis):
    tracer = Tracer(fake_redis, organization_id=str(uuid.uuid4()), name="run")
    await tracer.start()
    await tracer.end(status="error", payload={"error_code": "BOOM"})

    entries = await fake_redis.xrange(STREAM)
    end_event = json.loads(entries[-1][1]["data"])
    assert end_event["type"] == "agent_end"
    assert end_event["payload"]["status"] == "error"
    assert end_event["payload"]["error_code"] == "BOOM"
    assert end_event["payload"]["started_at"]
    assert end_event["payload"]["ended_at"]


@pytest.mark.asyncio
async def test_tracer_unique_trace_ids():
    import fakeredis.aioredis

    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    t1 = Tracer(r, organization_id="o", name="a")
    t2 = Tracer(r, organization_id="o", name="b")
    assert t1.trace_id != t2.trace_id
    await r.flushall()


# ─── ConnectionManager (org filtreli broadcast) ───────────

class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, message: str) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_broadcast_only_targets_matching_org():
    mgr = ConnectionManager()
    a1, a2, b1 = _FakeWS(), _FakeWS(), _FakeWS()

    await mgr.connect("org-a", a1)
    await mgr.connect("org-a", a2)
    await mgr.connect("org-b", b1)

    await mgr.broadcast("org-a", {"type": "token", "content": "hi"})

    assert len(a1.sent) == 1 and len(a2.sent) == 1
    assert len(b1.sent) == 0  # org-b event almamalı
    assert json.loads(a1.sent[0])["content"] == "hi"


@pytest.mark.asyncio
async def test_connect_accepts_and_counts():
    mgr = ConnectionManager()
    ws = _FakeWS()
    await mgr.connect("org-a", ws)
    assert ws.accepted is True
    assert mgr.connection_count("org-a") == 1


@pytest.mark.asyncio
async def test_disconnect_removes_connection():
    mgr = ConnectionManager()
    ws = _FakeWS()
    await mgr.connect("org-a", ws)
    await mgr.disconnect("org-a", ws)
    assert mgr.connection_count("org-a") == 0


@pytest.mark.asyncio
async def test_broadcast_to_empty_org_is_noop():
    mgr = ConnectionManager()
    await mgr.broadcast("nobody", {"type": "token"})  # patlamamalı
