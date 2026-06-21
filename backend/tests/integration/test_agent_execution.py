"""
Integration Testler — M9 Agent Execution

Kapsam:
  - Agent CRUD: oluştur, listele, güncelle, sil
  - RBAC: member oluşturamaz, admin oluşturabilir, başka org → 404
  - /run (sync): mock provider ile gerçek endpoint akışı
  - /run (SSE): stream=true → text/event-stream, done event alınıyor
  - Tool doğrulama: kayıtsız tool → 422
  - GET /agents/tools: kayıtlı tool listesi
  - Trace: run sonrası Redis'e event yazıldığı doğrulanıyor

NOT: LLM provider'lar mock'lanır — gerçek API çağrısı yapılmaz.
Docker stack ayakta olmalı (PostgreSQL, Redis). ClickHouse opsiyonel.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
)

pytestmark = pytest.mark.integration


# ─── Yardımcılar ──────────────────────────────────────────

def _make_mock_execute(content: str = "Mocked answer"):
    """
    AgentRunner._execute'u mock'lar — provider API çağrısı yapmaz.
    get_provider patch'i ile birlikte kullanılır.
    """
    from app.services.agent.base import AgentResult

    async def _mock(self, user_input: str) -> AgentResult:
        await self.tracer.start()
        await self.tracer.event("llm_call_start", {"model": self.config.model, "step": 1})
        await self.tracer.event("llm_call_end", {"finish_reason": "stop", "step": 1})
        await self.tracer.end(status="completed", payload={"steps": 1})
        return AgentResult(
            content=content,
            steps_taken=1,
            trace_id=self.tracer.trace_id,
            finish_reason="stop",
            total_usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    return _mock


def _mock_provider():
    """Test ortamında get_provider'ın döneceği sahte provider."""
    from app.services.providers.base import BaseLLMProvider
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.name = "openai"
    return provider


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
async def owner_client(client: AsyncClient):
    """Kayıtlı + login olmuş owner kullanıcısının client'ı."""
    email = f"agent-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


# ─── CRUD: Create ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_agent_as_admin(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/agents", json={
        "name": "test-agent",
        "system_prompt": "You are a test assistant.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_names": ["echo"],
    })
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["name"] == "test-agent"
    assert data["provider"] == "openai"
    assert "echo" in data["tool_names"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_agent_member_forbidden(client: AsyncClient):
    """Member rolündeki kullanıcı agent oluşturamaz → 403."""
    from tests.integration.auth_helpers import add_member

    owner_email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    owner_id = await register_and_verify(client, email=owner_email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(owner_id)

    member_email = f"mem-{uuid.uuid4().hex[:8]}@example.com"
    member_id = await register_and_verify(client, email=member_email, password="Test1234!", full_name="Mem")
    add_member(org_id, member_id, "member")

    await login_user(client, email=member_email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.post("/agents", json={
        "name": "should-fail",
        "system_prompt": "test",
        "provider": "openai",
        "model": "gpt-4o-mini",
    })
    assert resp.status_code == 403
    assert_error(resp.json(), "INSUFFICIENT_PERMISSIONS")


@pytest.mark.asyncio
async def test_create_agent_duplicate_name_conflict(owner_client):
    client, _, _ = owner_client
    payload = {
        "name": f"dup-agent-{uuid.uuid4().hex[:6]}",
        "system_prompt": "x",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    r1 = await client.post("/agents", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/agents", json=payload)
    assert r2.status_code == 409
    assert_error(r2.json(), "AGENT_NAME_CONFLICT")


@pytest.mark.asyncio
async def test_create_agent_unregistered_tool_rejected(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/agents", json={
        "name": "bad-tool-agent",
        "system_prompt": "x",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_names": ["definitely_not_registered"],
    })
    assert resp.status_code == 422
    assert_error(resp.json(), "TOOL_NOT_REGISTERED")


@pytest.mark.asyncio
async def test_create_agent_invalid_provider_rejected(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/agents", json={
        "name": "bad-provider",
        "system_prompt": "x",
        "provider": "chatgpt",
        "model": "gpt-4o-mini",
    })
    assert resp.status_code == 422


# ─── CRUD: List / Get ─────────────────────────────────────

@pytest.mark.asyncio
async def test_list_agents_returns_org_agents(owner_client):
    client, _, _ = owner_client
    name = f"list-test-{uuid.uuid4().hex[:6]}"
    await client.post("/agents", json={
        "name": name, "system_prompt": "x", "provider": "openai", "model": "gpt-4o-mini",
    })
    resp = await client.get("/agents")
    assert resp.status_code == 200
    data = assert_success(resp.json())
    names = [a["name"] for a in data]
    assert name in names


@pytest.mark.asyncio
async def test_get_agent_detail(owner_client):
    client, _, _ = owner_client
    name = f"detail-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "test", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    get_resp = await client.get(f"/agents/{agent_id}")
    assert get_resp.status_code == 200
    data = assert_success(get_resp.json())
    assert data["id"] == agent_id
    assert data["name"] == name


@pytest.mark.asyncio
async def test_get_agent_wrong_org_returns_404(owner_client, client: AsyncClient):
    """Başka org'un agent'ını isteyen kullanıcı → 404."""
    owner_c, _, _ = owner_client
    name = f"other-{uuid.uuid4().hex[:6]}"
    create_resp = await owner_c.post("/agents", json={
        "name": name, "system_prompt": "x", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    # Farklı org'a sahip kullanıcı
    email2 = f"other-user-{uuid.uuid4().hex[:8]}@example.com"
    user2_id = await register_and_verify(client, email=email2, password="Test1234!", full_name="U2")
    org2_id, _ = seed_organization(user2_id)
    await login_user(client, email=email2, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org2_id})

    resp = await client.get(f"/agents/{agent_id}")
    assert resp.status_code == 404


# ─── CRUD: Update / Delete ────────────────────────────────

@pytest.mark.asyncio
async def test_update_agent(owner_client):
    client, _, _ = owner_client
    name = f"upd-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "old", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    patch_resp = await client.patch(f"/agents/{agent_id}", json={
        "system_prompt": "new prompt",
        "max_steps": 20,
    })
    assert patch_resp.status_code == 200
    data = assert_success(patch_resp.json())
    assert data["system_prompt"] == "new prompt"
    assert data["max_steps"] == 20


@pytest.mark.asyncio
async def test_update_agent_exclude_unset(owner_client):
    """PATCH sadece gönderilen alanları günceller — gönderilmeyenler değişmez."""
    client, _, _ = owner_client
    name = f"upd2-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "original", "provider": "openai",
        "model": "gpt-4o-mini", "max_steps": 7,
    })
    agent_id = assert_success(create_resp.json())["id"]

    patch_resp = await client.patch(f"/agents/{agent_id}", json={"max_steps": 15})
    data = assert_success(patch_resp.json())
    assert data["max_steps"] == 15
    assert data["system_prompt"] == "original"  # değişmemeli


@pytest.mark.asyncio
async def test_delete_agent(owner_client):
    client, _, _ = owner_client
    name = f"del-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "x", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    del_resp = await client.delete(f"/agents/{agent_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/agents/{agent_id}")
    assert get_resp.status_code == 404


# ─── Tools listing ────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_available_tools(owner_client):
    client, _, _ = owner_client
    resp = await client.get("/agents/tools")
    assert resp.status_code == 200
    data = assert_success(resp.json())
    tool_names = [t["name"] for t in data]
    # Seçilebilir tool'lar görünür (web/self kategorileri)
    assert "web_search" in tool_names
    assert "think" in tool_names
    # F2: internal tool'lar gizli (kayıtlı ama listede yok)
    assert "echo" not in tool_names
    assert "calculator" not in tool_names
    assert "call_agent" not in tool_names
    # Her tool'un description, parameters ve category alanı olmalı
    for tool in data:
        assert "description" in tool
        assert "parameters" in tool
        assert "category" in tool


# ─── /run — sync (stream=false) ───────────────────────────

@pytest.mark.asyncio
async def test_run_agent_sync_returns_result(owner_client):
    """
    /run sync modu: _execute ve get_provider mock'lanır.
    Gerçek DB + Redis kullanılır; LLM çağrısı yoktur.
    """
    client, _, _ = owner_client
    name = f"run-sync-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name,
        "system_prompt": "You are helpful.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_names": ["echo"],
    })
    agent_id = assert_success(create_resp.json())["id"]

    with (
        patch("app.services.providers.factory.get_provider", return_value=_mock_provider()),
        patch("app.services.agent.runner.AgentRunner._execute", _make_mock_execute("Mocked answer")),
    ):
        run_resp = await client.post(f"/agents/{agent_id}/run", json={
            "input": "Hello!",
            "stream": False,
        })

    assert run_resp.status_code == 200
    data = assert_success(run_resp.json())
    assert data["content"] == "Mocked answer"
    assert data["steps_taken"] == 1
    assert "trace_id" in data
    assert data["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_run_inactive_agent_returns_422(owner_client):
    client, _, _ = owner_client
    name = f"inactive-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "x", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    await client.patch(f"/agents/{agent_id}", json={"is_active": False})

    run_resp = await client.post(f"/agents/{agent_id}/run", json={"input": "test", "stream": False})
    assert run_resp.status_code == 422
    assert_error(run_resp.json(), "AGENT_INACTIVE")


@pytest.mark.asyncio
async def test_run_nonexistent_agent_returns_404(owner_client):
    client, _, _ = owner_client
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/agents/{fake_id}/run", json={"input": "hi", "stream": False})
    assert resp.status_code == 404


# ─── /run — SSE (stream=true) ─────────────────────────────

@pytest.mark.asyncio
async def test_run_agent_sse_stream(owner_client):
    """SSE yanıtının text/event-stream döndüğünü ve 'done' event'i içerdiğini doğrular."""
    client, _, _ = owner_client
    name = f"run-sse-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "x", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    from app.services.agent.base import AgentStreamEvent

    async def mock_stream(self, user_input: str):
        await self.tracer.start()
        yield AgentStreamEvent(type="token", content="Hello")
        yield AgentStreamEvent(type="token", content=" world")
        yield AgentStreamEvent(
            type="done",
            trace_id=str(uuid.uuid4()),
            steps_taken=1,
            finish_reason="stop",
            total_usage={},
        )

    with (
        patch("app.services.providers.factory.get_provider", return_value=_mock_provider()),
        patch("app.services.agent.runner.AgentRunner.stream", mock_stream),
    ):
        run_resp = await client.post(f"/agents/{agent_id}/run", json={
            "input": "Hi",
            "stream": True,
        })

    assert run_resp.status_code == 200
    assert "text/event-stream" in run_resp.headers.get("content-type", "")

    body = run_resp.text
    assert "event: token" in body
    assert "event: done" in body

    # done event payload'unda trace_id olmalı
    done_data_line = next(
        (line for line in body.split("\n") if line.startswith("data:") and "trace_id" in line),
        None,
    )
    assert done_data_line is not None
    done_payload = json.loads(done_data_line.replace("data: ", ""))
    assert "trace_id" in done_payload


# ─── Trace: Redis'e event yazıldığını doğrula ─────────────

@pytest.mark.asyncio
async def test_run_agent_trace_written_to_redis(owner_client):
    """Agent çalıştırıldığında trace event'lerinin Redis Stream'e yazıldığını doğrular."""
    from app.core.redis import get_redis_pool
    from app.services.trace_collector import STREAM

    client, _, _ = owner_client
    name = f"trace-test-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/agents", json={
        "name": name, "system_prompt": "x", "provider": "openai", "model": "gpt-4o-mini",
    })
    agent_id = assert_success(create_resp.json())["id"]

    redis = await get_redis_pool()
    before_count = await redis.xlen(STREAM)

    with (
        patch("app.services.providers.factory.get_provider", return_value=_mock_provider()),
        patch("app.services.agent.runner.AgentRunner._execute", _make_mock_execute("traced")),
    ):
        run_resp = await client.post(f"/agents/{agent_id}/run", json={
            "input": "trace me",
            "stream": False,
        })

    assert run_resp.status_code == 200
    after_count = await redis.xlen(STREAM)
    # _make_mock_execute start + 2 event + end = 4 event yazar
    assert after_count >= before_count + 4
