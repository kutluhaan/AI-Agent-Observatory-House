"""
Faz 1 integration — kalıcı sohbet thread'leri.

Conversation CRUD, mesaj gönderme (SSE + sync, mock provider), çok-turlu hafıza,
ve kullanıcı/org izolasyonu. Gerçek PostgreSQL + Redis. Docker backend container içinde:

    docker compose -f docker-compose.dev.yml exec backend \\
        pytest tests/integration/test_conversations.py -v -m integration
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.providers.base import CompletionResult, StreamEvent
from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
)

pytestmark = pytest.mark.integration

_COMPLETE = "app.services.providers.openai_provider.OpenAIProvider.complete"
_STREAM = "app.services.providers.openai_provider.OpenAIProvider.stream"


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


# Patch hedefleri: streaming için async generator method
async def _fake_stream(self, messages, model, tools=None, temperature=0.7, max_tokens=None):
    yield StreamEvent(type="token", content="Hello ")
    yield StreamEvent(type="token", content="world")
    yield StreamEvent(type="done", finish_reason="stop")


async def _owner_with_agent(client: AsyncClient, prefix: str = "conv") -> str:
    """Owner + org + openai agent (echo tool). agent_id döner; token org'a switch'li."""
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    uid = await register_and_verify(client, email=email, password="Test1234!", full_name="Conv Owner")
    org_id, _ = seed_organization(uid, slug=f"{prefix}-{uuid.uuid4().hex[:8]}")
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    resp = await client.post("/agents", json={
        "name": f"Echo-{uuid.uuid4().hex[:6]}",
        "system_prompt": "You are helpful.",
        "provider": "openai",
        "model": "gpt-4o",
        "tool_names": ["echo"],
    })
    return assert_success(resp.json())["id"]


async def _independent_client():
    from app.core.redis import get_redis_pool
    from app.main import app
    await get_redis_pool()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def _platform_openai(monkeypatch):
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "sk-test")


# ─── CRUD ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_conversation(client):
    _require_db()
    agent_id = await _owner_with_agent(client)

    create = await client.post(f"/agents/{agent_id}/conversations")
    assert create.status_code == 201
    conv = assert_success(create.json())
    assert conv["title"] == "New chat"

    lst = await client.get(f"/agents/{agent_id}/conversations")
    assert lst.status_code == 200
    items = assert_success(lst.json())
    assert any(c["id"] == conv["id"] for c in items)


@pytest.mark.asyncio
async def test_send_message_persists_and_titles(client, _platform_openai):
    _require_db()
    agent_id = await _owner_with_agent(client)
    conv = assert_success((await client.post(f"/agents/{agent_id}/conversations")).json())
    cid = conv["id"]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_STREAM, _fake_stream)
        resp = await client.post(f"/conversations/{cid}/messages", json={"input": "research bürotime"})
    assert resp.status_code == 200

    # Reload — user + assistant mesajları kalıcı, başlık ilk mesajdan üretildi
    detail = assert_success((await client.get(f"/conversations/{cid}")).json())
    assert detail["title"].startswith("research bürotime")
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["content"] == "Hello world"
    assert assistant["segments"][0]["kind"] == "text"


@pytest.mark.asyncio
async def test_memory_passes_history(client, _platform_openai):
    _require_db()
    agent_id = await _owner_with_agent(client)
    cid = assert_success((await client.post(f"/agents/{agent_id}/conversations")).json())["id"]

    captured: list = []

    async def _capture_complete(self, messages, model, tools=None, temperature=0.7, max_tokens=None):
        captured.append(messages)
        return CompletionResult(content="ok", finish_reason="stop", usage={})

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_COMPLETE, _capture_complete)
        await client.post(f"/conversations/{cid}/messages", json={"input": "first question", "stream": False})
        await client.post(f"/conversations/{cid}/messages", json={"input": "second question", "stream": False})

    # İkinci çağrı geçmişi (1. user + 1. assistant) içermeli
    second = captured[1]
    contents = [m.content for m in second]
    assert "first question" in contents
    assert "ok" in contents  # önceki asistan cevabı
    assert "second question" in contents


@pytest.mark.asyncio
async def test_conversation_isolation_other_user(client, _platform_openai):
    _require_db()
    agent_id = await _owner_with_agent(client, prefix="owner")
    cid = assert_success((await client.post(f"/agents/{agent_id}/conversations")).json())["id"]

    # Bağımsız ikinci kullanıcı (ayrı cookie jar) — başkasının thread'ini görememeli
    other = await _independent_client()
    try:
        await _owner_with_agent(other, prefix="intruder")
        resp = await other.get(f"/conversations/{cid}")
        assert resp.status_code == 404
        assert_error(resp.json(), "CONVERSATION_NOT_FOUND")
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_rename_and_delete(client):
    _require_db()
    agent_id = await _owner_with_agent(client)
    cid = assert_success((await client.post(f"/agents/{agent_id}/conversations")).json())["id"]

    ren = await client.patch(f"/conversations/{cid}", json={"title": "My research"})
    assert ren.status_code == 200
    assert assert_success(ren.json())["title"] == "My research"

    dele = await client.delete(f"/conversations/{cid}")
    assert dele.status_code == 204

    gone = await client.get(f"/conversations/{cid}")
    assert gone.status_code == 404
