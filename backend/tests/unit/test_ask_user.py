"""
Faz 2 unit — ask_user (AskUserQuestion) + yeni tool'lar.

Runner ask_user'ı yakalar: soru oluşturur, kullanıcı yanıtını bekler (HITL engine),
yanıtı tool sonucu olarak agent'a geri besler.
"""
import asyncio
import uuid

import pytest

from app.services.agent.base import AgentConfig
from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.runner import AgentRunner
from app.services.agent.tools.builtin import register_builtin_tools
from app.services.hitl import HITLEngine
from app.services.providers.base import CompletionResult
from app.services.trace_collector import Tracer


@pytest.fixture(autouse=True)
def _register_tools():
    register_builtin_tools()  # ask_user dahil tool tanımları registry'de olsun


@pytest.fixture
async def fake_redis():
    import fakeredis.aioredis

    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.flushall()


def _cfg() -> AgentConfig:
    return AgentConfig(
        agent_id=uuid.uuid4(), org_id=uuid.uuid4(), name="t", system_prompt="",
        provider="openai", model="m", temperature=0.7, max_tokens=None,
        max_steps=5, timeout_seconds=60, tool_names=["ask_user"],
    )


class _AskThenStop:
    name = "openai"
    supports_tools = True

    def __init__(self) -> None:
        self.calls: list = []

    async def complete(self, messages, model, tools=None, temperature=0.7, max_tokens=None):
        self.calls.append(messages)
        if len(self.calls) == 1:
            return CompletionResult(
                content="",
                finish_reason="tool_calls",
                tool_calls=[{
                    "id": "c1",
                    "name": "ask_user",
                    "arguments": {"question": "Pick one", "options": ["A", "B"], "multi": False},
                }],
                usage={},
            )
        return CompletionResult(content="Final answer", finish_reason="stop", usage={})

    async def stream(self, *a, **k):
        yield  # interface gereği; bu testte kullanılmaz

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_ask_user_sync_flow(fake_redis):
    engine = HITLEngine(fake_redis)
    provider = _AskThenStop()
    runner = AgentRunner(
        _cfg(), provider, Tracer(fake_redis, organization_id="org", name="t"), hitl=engine
    )

    task = asyncio.create_task(runner.run("hello"))

    # Soru oluşana kadar bekle, sonra yanıtı gönder
    for _ in range(100):
        if engine._pending:
            break
        await asyncio.sleep(0.02)
    request_id = next(iter(engine._pending))

    # İstek question kind'ında ve soru/seçenekleri taşıyor
    req = await engine.get(request_id)
    assert req.kind == "question"
    assert req.tool_arguments["question"] == "Pick one"

    await engine.submit_answer(request_id, "A")

    result = await task
    assert result.content == "Final answer"

    # İkinci LLM çağrısı yanıtı tool mesajı olarak görmeli
    second_call = provider.calls[1]
    assert any(m.role == "tool" and m.content == "A" for m in second_call)


@pytest.mark.asyncio
async def test_new_tools_registered():
    register_builtin_tools()
    for name in ("think", "write_todos", "ask_user"):
        handler = ToolRegistry.get(name)
        assert handler.name == name

    ctx = ToolContext(org_id=uuid.uuid4(), trace_id="t", db=None, redis=None)
    assert await ToolRegistry.get("think").handler(ctx, thought="hmm") == "Acknowledged."
    out = await ToolRegistry.get("write_todos").handler(
        ctx, todos=[{"content": "a", "status": "completed"}, {"content": "b", "status": "pending"}]
    )
    assert "1 completed" in out
