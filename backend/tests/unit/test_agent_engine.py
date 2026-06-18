"""
Unit Testler — M9 Agent Engine

Kapsam:
  - ToolRegistry: kayıt, çakışma tespiti, tanımsız tool hatası, build_definitions
  - AgentStreamEvent.to_sse(): SSE format doğrulama
  - AgentRunner.run(): stop, tool_call döngüsü, max_steps koruması, timeout
  - AgentRunner.stream(): token akışı ve tool_call event'leri
  - Calculator: güvenli aritmetik ve hata yönetimi
  - Tracer: parent_trace_id alanı (M8 geriye dönük uyumluluk)

Tüm LLM çağrıları mock'lanır; Redis için fakeredis kullanılır; DB gerektirmez.
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
    AgentMaxStepsError,
    AgentStreamEvent,
    AgentTimeoutError,
)
from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.runner import AgentRunner
from app.services.providers.base import (
    BaseLLMProvider,
    CompletionResult,
    Message,
    StreamEvent,
    ToolDefinition,
)
from app.services.trace_collector import STREAM, Tracer


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


def make_config(
    agent_id: uuid.UUID,
    org_id: uuid.UUID,
    tool_names: list[str] | None = None,
    max_steps: int = 5,
    timeout_seconds: int = 30,
) -> AgentConfig:
    return AgentConfig(
        agent_id=agent_id,
        org_id=org_id,
        name="test-agent",
        system_prompt="You are a test assistant.",
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=None,
        max_steps=max_steps,
        timeout_seconds=timeout_seconds,
        tool_names=tool_names or [],
    )


def make_tracer(fake_redis, org_id: uuid.UUID) -> Tracer:
    return Tracer(fake_redis, organization_id=str(org_id), name="test-run")


def make_provider_stop(content: str = "Hello!") -> BaseLLMProvider:
    """finish_reason=stop dönen provider mock'u."""
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(return_value=CompletionResult(
        content=content,
        finish_reason="stop",
        tool_calls=[],
        usage={"prompt_tokens": 10, "completion_tokens": 5},
    ))
    return provider


def make_provider_tool_then_stop(
    tool_name: str,
    tool_args: dict[str, Any],
    final_content: str = "Done!",
) -> BaseLLMProvider:
    """İlk çağrıda tool_calls, ikincisinde stop dönen provider."""
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(side_effect=[
        CompletionResult(
            content="",
            finish_reason="tool_calls",
            tool_calls=[{"id": "call_1", "name": tool_name, "arguments": tool_args}],
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        ),
        CompletionResult(
            content=final_content,
            finish_reason="stop",
            tool_calls=[],
            usage={"prompt_tokens": 15, "completion_tokens": 8},
        ),
    ])
    return provider


# ─── ToolRegistry ─────────────────────────────────────────

def test_tool_registry_register_and_get():
    ToolRegistry._reset()

    @ToolRegistry.register("test_tool", "A test tool", {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    })
    async def handler(ctx: ToolContext, x: str) -> str:
        return x

    tool = ToolRegistry.get("test_tool")
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    ToolRegistry._reset()


def test_tool_registry_duplicate_raises():
    ToolRegistry._reset()

    @ToolRegistry.register("dup", "first", {"type": "object", "properties": {}})
    async def h1(ctx, **_): ...

    with pytest.raises(ValueError, match="zaten kayıtlı"):
        @ToolRegistry.register("dup", "second", {"type": "object", "properties": {}})
        async def h2(ctx, **_): ...

    ToolRegistry._reset()


def test_tool_registry_get_unknown_raises():
    ToolRegistry._reset()
    with pytest.raises(KeyError):
        ToolRegistry.get("nonexistent")
    ToolRegistry._reset()


def test_tool_registry_build_definitions():
    ToolRegistry._reset()

    @ToolRegistry.register("my_tool", "desc", {
        "type": "object",
        "properties": {"a": {"type": "integer"}},
        "required": ["a"],
    })
    async def h(ctx, a: int) -> str: ...

    defs = ToolRegistry.build_definitions(["my_tool"])
    assert len(defs) == 1
    assert isinstance(defs[0], ToolDefinition)
    assert defs[0].name == "my_tool"
    ToolRegistry._reset()


def test_tool_registry_build_definitions_unknown_raises():
    ToolRegistry._reset()
    with pytest.raises(KeyError):
        ToolRegistry.build_definitions(["ghost"])
    ToolRegistry._reset()


# ─── AgentStreamEvent SSE format ──────────────────────────

def test_stream_event_token_sse():
    ev = AgentStreamEvent(type="token", content="hello", step=1)
    sse = ev.to_sse()
    assert sse.startswith("event: token\n")
    assert "data:" in sse
    payload = json.loads(sse.split("data: ", 1)[1].strip())
    assert payload["content"] == "hello"
    assert payload["step"] == 1


def test_stream_event_done_sse():
    ev = AgentStreamEvent(type="done", trace_id="abc-123", steps_taken=2, finish_reason="stop")
    sse = ev.to_sse()
    payload = json.loads(sse.split("data: ", 1)[1].strip())
    assert payload["trace_id"] == "abc-123"
    assert payload["steps_taken"] == 2


def test_stream_event_none_fields_excluded():
    ev = AgentStreamEvent(type="token", content="x")
    payload = json.loads(ev.to_sse().split("data: ", 1)[1].strip())
    assert "tool_name" not in payload
    assert "error_code" not in payload


# ─── AgentRunner.run() — stop ─────────────────────────────

@pytest.mark.asyncio
async def test_runner_run_stop(fake_redis, org_id, agent_id):
    ToolRegistry._reset()
    config = make_config(agent_id, org_id)
    provider = make_provider_stop("Hi there!")
    tracer = make_tracer(fake_redis, org_id)

    runner = AgentRunner(config=config, provider=provider, tracer=tracer)
    result = await runner.run("Hello")

    assert result.content == "Hi there!"
    assert result.steps_taken == 1
    assert result.finish_reason == "stop"
    assert result.trace_id == tracer.trace_id
    # 1 provider.complete çağrısı yapılmalı
    provider.complete.assert_awaited_once()
    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_run_emits_trace_events(fake_redis, org_id, agent_id):
    ToolRegistry._reset()
    config = make_config(agent_id, org_id)
    provider = make_provider_stop()
    tracer = make_tracer(fake_redis, org_id)

    runner = AgentRunner(config=config, provider=provider, tracer=tracer)
    await runner.run("test")

    entries = await fake_redis.xrange(STREAM)
    events = [json.loads(f["data"]) for _, f in entries]
    types = [e["type"] for e in events]

    assert "agent_start" in types
    assert "llm_call_start" in types
    assert "llm_call_end" in types
    assert "agent_end" in types
    ToolRegistry._reset()


# ─── AgentRunner.run() — tool call loop ───────────────────

@pytest.mark.asyncio
async def test_runner_run_tool_call_loop(fake_redis, org_id, agent_id):
    ToolRegistry._reset()

    @ToolRegistry.register("echo", "echo", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def echo(ctx, text: str) -> str:
        return text

    config = make_config(agent_id, org_id, tool_names=["echo"])
    provider = make_provider_tool_then_stop("echo", {"text": "world"}, "Final answer.")
    tracer = make_tracer(fake_redis, org_id)

    runner = AgentRunner(config=config, provider=provider, tracer=tracer)
    result = await runner.run("use echo")

    assert result.content == "Final answer."
    assert result.steps_taken == 2  # step 1: tool_calls, step 2: stop
    assert provider.complete.await_count == 2

    # tool_call_start ve tool_call_end trace'de olmalı
    entries = await fake_redis.xrange(STREAM)
    types = [json.loads(f["data"])["type"] for _, f in entries]
    assert "tool_call_start" in types
    assert "tool_call_end" in types
    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_tool_result_injected_into_messages(fake_redis, org_id, agent_id):
    """Provider ikinci çağrıda tool result'ı message geçmişinde görüyor olmalı."""
    ToolRegistry._reset()

    @ToolRegistry.register("echo2", "echo", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def echo2(ctx, text: str) -> str:
        return f"echoed:{text}"

    config = make_config(agent_id, org_id, tool_names=["echo2"])
    provider = make_provider_tool_then_stop("echo2", {"text": "ping"})
    tracer = make_tracer(fake_redis, org_id)

    runner = AgentRunner(config=config, provider=provider, tracer=tracer)
    await runner.run("test")

    # İkinci complete çağrısında mesaj geçmişinde tool result olmalı
    second_call_messages: list[Message] = provider.complete.call_args_list[1][0][0]
    roles = [m.role for m in second_call_messages]
    assert "tool" in roles

    tool_msg = next(m for m in second_call_messages if m.role == "tool")
    assert tool_msg.content == "echoed:ping"
    ToolRegistry._reset()


# ─── AgentRunner.run() — max_steps ────────────────────────

@pytest.mark.asyncio
async def test_runner_max_steps_raises(fake_redis, org_id, agent_id):
    ToolRegistry._reset()

    @ToolRegistry.register("loop_tool", "loops", {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    })
    async def loop_tool(ctx, x: str) -> str:
        return "loop"

    # Her zaman tool_calls döner → sonsuz döngü olurdu
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(return_value=CompletionResult(
        content="",
        finish_reason="tool_calls",
        tool_calls=[{"id": "c", "name": "loop_tool", "arguments": {"x": "y"}}],
        usage={},
    ))

    config = make_config(agent_id, org_id, tool_names=["loop_tool"], max_steps=3)
    tracer = make_tracer(fake_redis, org_id)

    runner = AgentRunner(config=config, provider=provider, tracer=tracer)
    with pytest.raises(AgentMaxStepsError) as exc_info:
        await runner.run("loop")

    assert exc_info.value.code == "AGENT_MAX_STEPS_EXCEEDED"
    assert provider.complete.await_count == 3  # tam max_steps kadar çağrılmalı

    # Trace'de max_steps_exceeded kaydedilmeli
    entries = await fake_redis.xrange(STREAM)
    types_payloads = [json.loads(f["data"]) for _, f in entries]
    end_event = next(e for e in types_payloads if e["type"] == "agent_end")
    assert end_event["payload"]["status"] == "max_steps_exceeded"
    ToolRegistry._reset()


# ─── AgentRunner.run() — timeout ──────────────────────────

@pytest.mark.asyncio
async def test_runner_timeout_raises(fake_redis, org_id, agent_id):
    ToolRegistry._reset()

    async def slow_complete(*args, **kwargs):
        await asyncio.sleep(10)  # çok yavaş
        return CompletionResult(content="late", finish_reason="stop", tool_calls=[], usage={})

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = slow_complete

    config = make_config(agent_id, org_id, timeout_seconds=1)
    tracer = make_tracer(fake_redis, org_id)

    runner = AgentRunner(config=config, provider=provider, tracer=tracer)
    with pytest.raises(AgentTimeoutError) as exc_info:
        await runner.run("slow")

    assert exc_info.value.code == "AGENT_TIMEOUT"
    ToolRegistry._reset()


# ─── AgentRunner.run() — unknown tool ─────────────────────

@pytest.mark.asyncio
async def test_runner_unknown_tool_returns_error_string(fake_redis, org_id, agent_id):
    """Kayıtsız tool çağrılırsa AgentToolError yükseltilir ve mesaja yansır."""
    ToolRegistry._reset()

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.complete = AsyncMock(side_effect=[
        CompletionResult(
            content="",
            finish_reason="tool_calls",
            tool_calls=[{"id": "c", "name": "ghost_tool", "arguments": {}}],
            usage={},
        ),
    ])

    config = make_config(agent_id, org_id, tool_names=[])
    tracer = make_tracer(fake_redis, org_id)
    runner = AgentRunner(config=config, provider=provider, tracer=tracer)

    from app.services.agent.base import AgentToolError
    with pytest.raises(AgentToolError):
        await runner.run("use ghost")
    ToolRegistry._reset()


# ─── AgentRunner.stream() ─────────────────────────────────

@pytest.mark.asyncio
async def test_runner_stream_emits_token_and_done(fake_redis, org_id, agent_id):
    ToolRegistry._reset()

    async def mock_stream(*args, **kwargs) -> AsyncIterator[StreamEvent]:
        yield StreamEvent(type="token", content="Hello")
        yield StreamEvent(type="token", content=" world")
        yield StreamEvent(type="done", finish_reason="stop")

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.stream = mock_stream

    config = make_config(agent_id, org_id)
    tracer = make_tracer(fake_redis, org_id)
    runner = AgentRunner(config=config, provider=provider, tracer=tracer)

    events = []
    async for ev in runner.stream("hi"):
        events.append(ev)

    token_events = [e for e in events if e.type == "token"]
    done_events = [e for e in events if e.type == "done"]

    assert len(token_events) == 2
    assert token_events[0].content == "Hello"
    assert token_events[1].content == " world"
    assert len(done_events) == 1
    assert done_events[0].finish_reason == "stop"
    ToolRegistry._reset()


@pytest.mark.asyncio
async def test_runner_stream_tool_call_events(fake_redis, org_id, agent_id):
    ToolRegistry._reset()

    @ToolRegistry.register("echo_s", "echo", {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    })
    async def echo_s(ctx, text: str) -> str:
        return text

    call_done = False

    async def mock_stream(*args, **kwargs) -> AsyncIterator[StreamEvent]:
        nonlocal call_done
        if not call_done:
            call_done = True
            yield StreamEvent(type="tool_call", tool_call={"id": "c1", "name": "echo_s", "arguments": {"text": "hi"}})
            yield StreamEvent(type="done", finish_reason="tool_calls")
        else:
            yield StreamEvent(type="token", content="Result!")
            yield StreamEvent(type="done", finish_reason="stop")

    provider = AsyncMock(spec=BaseLLMProvider)
    provider.stream = mock_stream

    config = make_config(agent_id, org_id, tool_names=["echo_s"])
    tracer = make_tracer(fake_redis, org_id)
    runner = AgentRunner(config=config, provider=provider, tracer=tracer)

    types = []
    async for ev in runner.stream("use echo"):
        types.append(ev.type)

    assert "tool_call_start" in types
    assert "tool_call_end" in types
    assert "done" in types
    ToolRegistry._reset()


# ─── Calculator tool (güvenli eval) ───────────────────────

@pytest.mark.asyncio
async def test_calculator_basic_arithmetic():
    from app.services.agent.tools.builtin import _safe_eval
    assert _safe_eval("2 + 3") == 5.0
    assert _safe_eval("10 / 2") == 5.0
    assert _safe_eval("2 ** 8") == 256.0
    assert _safe_eval("(3 + 4) * 2") == 14.0


@pytest.mark.asyncio
async def test_calculator_rejects_non_arithmetic():
    from app.services.agent.tools.builtin import _safe_eval
    with pytest.raises(ValueError):
        _safe_eval("__import__('os').system('echo hi')")
    with pytest.raises(ValueError):
        _safe_eval("'hello'")  # string constant


# ─── Tracer parent_trace_id (M8 geriye dönük uyumluluk) ───

@pytest.mark.asyncio
async def test_tracer_parent_trace_id_propagated(fake_redis, org_id):
    parent_id = str(uuid.uuid4())
    tracer = Tracer(
        fake_redis,
        organization_id=str(org_id),
        name="sub-agent",
        parent_trace_id=parent_id,
    )
    await tracer.start()

    entries = await fake_redis.xrange(STREAM)
    event = json.loads(entries[0][1]["data"])
    assert event.get("parent_trace_id") == parent_id


@pytest.mark.asyncio
async def test_tracer_without_parent_no_field(fake_redis, org_id):
    tracer = Tracer(fake_redis, organization_id=str(org_id), name="root")
    await tracer.start()

    entries = await fake_redis.xrange(STREAM)
    event = json.loads(entries[0][1]["data"])
    assert "parent_trace_id" not in event
