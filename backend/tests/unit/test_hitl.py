"""
Unit Testler — M10 HITL Engine

Kapsam:
  - HITLEngine.create_request(): Redis'e yazar, request_id döner
  - HITLEngine.wait_for_resolution(): Event bekler; çözülünce HITLResolution döner
  - HITLEngine.resolve(): approved / rejected / modified akışları
  - HITLEngine.get(): Redis'ten okur
  - Timeout: HITL_TIMEOUT aşılınca HITLTimeoutError
  - Hata durumları: HITLNotFoundError, HITLAlreadyResolvedError
  - AgentRunner HITL gate: approved devam, rejected hata, modified argüman güncelleme

Tüm testlerde fakeredis kullanılır; LLM mock'lanır.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agent.base import (
    AgentConfig,
    AgentStreamEvent,
    HITLRejectedError,
    HITLTimeoutError,
)
from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.runner import AgentRunner
from app.services.hitl import (
    HITLAlreadyResolvedError,
    HITLEngine,
    HITLNotFoundError,
    HITLResolution,
)
from app.services.providers.base import (
    BaseLLMProvider,
    CompletionResult,
    StreamEvent,
)
from app.services.trace_collector import Tracer


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
async def fake_redis():
    import fakeredis.aioredis
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.flushall()


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def agent_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def hitl_engine(fake_redis):
    return HITLEngine(fake_redis)


@pytest.fixture
def tracer(fake_redis, org_id):
    return Tracer(redis=fake_redis, organization_id=str(org_id), name="test-hitl")


def make_config(agent_id, org_id, tool_names=None, hitl_tool_names=None):
    return AgentConfig(
        agent_id=agent_id,
        org_id=org_id,
        name="hitl-test",
        system_prompt="You are helpful.",
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=None,
        max_steps=5,
        timeout_seconds=30,
        tool_names=tool_names or [],
        hitl_tool_names=hitl_tool_names or [],
    )


# ─── HITLEngine core ──────────────────────────────────────

@pytest.mark.asyncio
async def test_create_request_writes_to_redis(hitl_engine, fake_redis):
    request_id = await hitl_engine.create_request(
        trace_id="trace-123",
        org_id="org-abc",
        tool_name="echo",
        tool_arguments={"text": "hi"},
    )
    assert request_id

    raw = await fake_redis.get(f"hitl:{request_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["request_id"] == request_id
    assert data["tool_name"] == "echo"
    assert data["status"] == "pending"
    assert data["tool_arguments"] == {"text": "hi"}


@pytest.mark.asyncio
async def test_get_returns_request(hitl_engine):
    request_id = await hitl_engine.create_request(
        trace_id="t1", org_id="o1", tool_name="calc", tool_arguments={"expr": "1+1"},
    )
    req = await hitl_engine.get(request_id)
    assert req is not None
    assert req.request_id == request_id
    assert req.status == "pending"


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown(hitl_engine):
    req = await hitl_engine.get("nonexistent-id")
    assert req is None


@pytest.mark.asyncio
async def test_resolve_approved_wakes_waiter(hitl_engine):
    request_id = await hitl_engine.create_request(
        trace_id="t", org_id="o", tool_name="echo", tool_arguments={"text": "x"},
    )

    async def _approve():
        await asyncio.sleep(0.05)
        await hitl_engine.resolve(request_id, "approved")

    approve_task = asyncio.create_task(_approve())
    resolution = await hitl_engine.wait_for_resolution(request_id)
    await approve_task

    assert resolution.action == "approved"
    assert resolution.modified_arguments is None


@pytest.mark.asyncio
async def test_resolve_rejected_wakes_waiter(hitl_engine):
    request_id = await hitl_engine.create_request(
        trace_id="t", org_id="o", tool_name="echo", tool_arguments={"text": "x"},
    )

    async def _reject():
        await asyncio.sleep(0.05)
        await hitl_engine.resolve(request_id, "rejected", reason="too risky")

    reject_task = asyncio.create_task(_reject())
    resolution = await hitl_engine.wait_for_resolution(request_id)
    await reject_task

    assert resolution.action == "rejected"
    assert resolution.reason == "too risky"


@pytest.mark.asyncio
async def test_resolve_modified_returns_new_arguments(hitl_engine):
    request_id = await hitl_engine.create_request(
        trace_id="t", org_id="o", tool_name="echo", tool_arguments={"text": "original"},
    )

    async def _modify():
        await asyncio.sleep(0.05)
        await hitl_engine.resolve(
            request_id, "modified", modified_arguments={"text": "changed"}
        )

    mod_task = asyncio.create_task(_modify())
    resolution = await hitl_engine.wait_for_resolution(request_id)
    await mod_task

    assert resolution.action == "modified"
    assert resolution.modified_arguments == {"text": "changed"}


@pytest.mark.asyncio
async def test_resolve_updates_redis_status(hitl_engine, fake_redis):
    request_id = await hitl_engine.create_request(
        trace_id="t", org_id="o", tool_name="echo", tool_arguments={},
    )

    async def _approve():
        await asyncio.sleep(0.05)
        await hitl_engine.resolve(request_id, "approved")

    task = asyncio.create_task(_approve())
    await hitl_engine.wait_for_resolution(request_id)
    await task

    raw = await fake_redis.get(f"hitl:{request_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["status"] == "approved"


@pytest.mark.asyncio
async def test_resolve_not_found_raises(hitl_engine):
    with pytest.raises(HITLNotFoundError):
        await hitl_engine.resolve("does-not-exist", "approved")


@pytest.mark.asyncio
async def test_resolve_already_resolved_raises(hitl_engine):
    request_id = await hitl_engine.create_request(
        trace_id="t", org_id="o", tool_name="echo", tool_arguments={},
    )

    async def _approve():
        await asyncio.sleep(0.05)
        await hitl_engine.resolve(request_id, "approved")

    task = asyncio.create_task(_approve())
    await hitl_engine.wait_for_resolution(request_id)
    await task

    with pytest.raises(HITLAlreadyResolvedError) as exc_info:
        await hitl_engine.resolve(request_id, "rejected")
    assert exc_info.value.current_status == "approved"


@pytest.mark.asyncio
async def test_wait_for_resolution_timeout(hitl_engine):
    """Gerçek 10 dk timeout yerine patch ile kısa timeout."""
    request_id = await hitl_engine.create_request(
        trace_id="t", org_id="o", tool_name="echo", tool_arguments={},
    )
    with patch("app.services.hitl.HITL_TIMEOUT", 0.05):
        with pytest.raises(HITLTimeoutError):
            await hitl_engine.wait_for_resolution(request_id)


# ─── AgentRunner HITL integration ─────────────────────────

@pytest.mark.asyncio
async def test_runner_run_hitl_approved(fake_redis, org_id, agent_id):
    """HITL approved: runner tool çalıştırır ve result döner."""
    ToolRegistry._reset()

    @ToolRegistry.register("guarded_echo", "guarded echo", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def guarded_echo(ctx, text: str) -> str:
        return f"ECHO:{text}"

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(side_effect=[
        CompletionResult(
            content="",
            finish_reason="tool_calls",
            tool_calls=[{"id": "c1", "name": "guarded_echo", "arguments": {"text": "hello"}}],
            usage={},
        ),
        CompletionResult(
            content="Done.",
            finish_reason="stop",
            tool_calls=[],
            usage={},
        ),
    ])

    hitl = HITLEngine(fake_redis)
    config = make_config(agent_id, org_id, tool_names=["guarded_echo"], hitl_tool_names=["guarded_echo"])
    tracer = Tracer(redis=fake_redis, organization_id=str(org_id), name="test")
    runner = AgentRunner(config=config, provider=provider, tracer=tracer, hitl=hitl)

    async def _approve():
        # Bekle: runner create_request çağırdıktan sonra approve yap
        for _ in range(50):
            await asyncio.sleep(0.02)
            if hitl._pending:
                rid = next(iter(hitl._pending))
                await hitl.resolve(rid, "approved")
                return

    approve_task = asyncio.create_task(_approve())
    result = await runner.run("echo hello")
    await approve_task

    assert result.content == "Done."
    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_run_hitl_rejected(fake_redis, org_id, agent_id):
    """HITL rejected: runner HITLRejectedError fırlatır."""
    ToolRegistry._reset()

    @ToolRegistry.register("risky_tool", "risky", {
        "type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"],
    })
    async def risky_tool(ctx, x: str) -> str:
        return x

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(return_value=CompletionResult(
        content="",
        finish_reason="tool_calls",
        tool_calls=[{"id": "c1", "name": "risky_tool", "arguments": {"x": "bad"}}],
        usage={},
    ))

    hitl = HITLEngine(fake_redis)
    config = make_config(agent_id, org_id, tool_names=["risky_tool"], hitl_tool_names=["risky_tool"])
    tracer = Tracer(redis=fake_redis, organization_id=str(org_id), name="test")
    runner = AgentRunner(config=config, provider=provider, tracer=tracer, hitl=hitl)

    async def _reject():
        for _ in range(50):
            await asyncio.sleep(0.02)
            if hitl._pending:
                rid = next(iter(hitl._pending))
                await hitl.resolve(rid, "rejected", reason="not allowed")
                return

    reject_task = asyncio.create_task(_reject())
    with pytest.raises(HITLRejectedError):
        await runner.run("do risky thing")
    await reject_task

    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_run_hitl_modified(fake_redis, org_id, agent_id):
    """HITL modified: runner modified argümanlarla tool'u çalıştırır."""
    ToolRegistry._reset()
    received: list[str] = []

    @ToolRegistry.register("mod_echo", "modifiable echo", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def mod_echo(ctx, text: str) -> str:
        received.append(text)
        return f"ECHO:{text}"

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(side_effect=[
        CompletionResult(
            content="",
            finish_reason="tool_calls",
            tool_calls=[{"id": "c1", "name": "mod_echo", "arguments": {"text": "original"}}],
            usage={},
        ),
        CompletionResult(content="Done.", finish_reason="stop", tool_calls=[], usage={}),
    ])

    hitl = HITLEngine(fake_redis)
    config = make_config(agent_id, org_id, tool_names=["mod_echo"], hitl_tool_names=["mod_echo"])
    tracer = Tracer(redis=fake_redis, organization_id=str(org_id), name="test")
    runner = AgentRunner(config=config, provider=provider, tracer=tracer, hitl=hitl)

    async def _modify():
        for _ in range(50):
            await asyncio.sleep(0.02)
            if hitl._pending:
                rid = next(iter(hitl._pending))
                await hitl.resolve(rid, "modified", modified_arguments={"text": "modified"})
                return

    modify_task = asyncio.create_task(_modify())
    result = await runner.run("echo something")
    await modify_task

    assert received == ["modified"]
    assert result.content == "Done."
    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_stream_hitl_events(fake_redis, org_id, agent_id):
    """Stream path: hitl_requested ve hitl_resolved event'leri yield edilir."""
    ToolRegistry._reset()

    @ToolRegistry.register("stream_guarded", "guarded", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def stream_guarded(ctx, text: str) -> str:
        return text

    call_count = 0

    async def mock_stream(*args, **kwargs) -> AsyncIterator[StreamEvent]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield StreamEvent(
                type="tool_call",
                tool_call={"id": "c1", "name": "stream_guarded", "arguments": {"text": "hi"}},
            )
            yield StreamEvent(type="done", finish_reason="tool_calls")
        else:
            yield StreamEvent(type="token", content="Result!")
            yield StreamEvent(type="done", finish_reason="stop")

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.stream = mock_stream

    hitl = HITLEngine(fake_redis)
    config = make_config(agent_id, org_id, tool_names=["stream_guarded"], hitl_tool_names=["stream_guarded"])
    tracer = Tracer(redis=fake_redis, organization_id=str(org_id), name="test")
    runner = AgentRunner(config=config, provider=provider, tracer=tracer, hitl=hitl)

    events: list[AgentStreamEvent] = []
    hitl_req_id: list[str] = []

    async def _collect():
        async for ev in runner.stream("go"):
            events.append(ev)
            if ev.type == "hitl_requested" and ev.hitl_request_id:
                hitl_req_id.append(ev.hitl_request_id)
                # Approve after collecting the event
                await hitl.resolve(ev.hitl_request_id, "approved")

    await _collect()

    types = [e.type for e in events]
    assert "hitl_requested" in types
    assert "hitl_resolved" in types
    assert "done" in types
    assert len(hitl_req_id) == 1

    hitl_ev = next(e for e in events if e.type == "hitl_requested")
    assert hitl_ev.tool_name == "stream_guarded"
    assert hitl_ev.hitl_request_id == hitl_req_id[0]

    resolved_ev = next(e for e in events if e.type == "hitl_resolved")
    assert resolved_ev.hitl_action == "approved"

    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_no_hitl_without_engine(fake_redis, org_id, agent_id):
    """hitl=None iken hitl_tool_names ayarlı olsa bile tool normal çalışır."""
    ToolRegistry._reset()

    @ToolRegistry.register("bypass_echo", "bypass", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def bypass_echo(ctx, text: str) -> str:
        return text

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(side_effect=[
        CompletionResult(
            content="",
            finish_reason="tool_calls",
            tool_calls=[{"id": "c1", "name": "bypass_echo", "arguments": {"text": "x"}}],
            usage={},
        ),
        CompletionResult(content="Done.", finish_reason="stop", tool_calls=[], usage={}),
    ])

    config = make_config(agent_id, org_id, tool_names=["bypass_echo"], hitl_tool_names=["bypass_echo"])
    tracer = Tracer(redis=fake_redis, organization_id=str(org_id), name="test")
    # hitl=None — HITL engine inject edilmemiş
    runner = AgentRunner(config=config, provider=provider, tracer=tracer, hitl=None)

    result = await runner.run("go")
    assert result.content == "Done."
    ToolRegistry._reset()
