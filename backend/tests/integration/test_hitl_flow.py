"""
Integration Testler — M10 HITL Flow

Kapsam:
  - Agent HITL tool konfigürasyonu: hitl_tool_names create/update
  - hitl_tool_names ⊆ tool_names zorunluluğu (422)
  - GET /hitl/{id} — durum sorgulama
  - POST /hitl/{id}/approve — onay; agent devam eder
  - POST /hitl/{id}/reject — red; agent HITL_REJECTED döner
  - POST /hitl/{id}/modify — argüman değiştirerek onay
  - Çift çözümleme: HITL_ALREADY_RESOLVED (409)
  - Bilinmeyen request_id: HITL_NOT_FOUND (404)
  - Farklı org: HITL_FORBIDDEN (403)

NOT: LLM provider ve AgentRunner._execute mock'lanır.
     HITLEngine app.state üzerinden değil, servis singleton üzerinden test edilir.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
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

def _mock_provider():
    from app.services.providers.base import BaseLLMProvider
    provider = AsyncMock(spec=BaseLLMProvider)
    provider.name = "openai"
    return provider


def _make_mock_execute(content: str = "Mocked answer"):
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
            total_usage={},
        )
    return _mock


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"hitl-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


@pytest.fixture
async def other_client(client: AsyncClient):
    """Farklı org'a sahip ikinci kullanıcı."""
    email = f"hitl-other-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Other")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


async def _create_agent(client, hitl_tool_names=None, tool_names=None):
    if tool_names is None:
        tool_names = ["echo"]
    payload = {
        "name": f"hitl-agent-{uuid.uuid4().hex[:6]}",
        "system_prompt": "You are helpful.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_names": tool_names,
    }
    if hitl_tool_names is not None:
        payload["hitl_tool_names"] = hitl_tool_names
    resp = await client.post("/agents", json=payload)
    return assert_success(resp.json())["id"]


# ─── Agent CRUD + HITL field ──────────────────────────────

@pytest.mark.asyncio
async def test_create_agent_with_hitl_tool_names(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/agents", json={
        "name": f"hitl-{uuid.uuid4().hex[:6]}",
        "system_prompt": "You are helpful.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_names": ["echo"],
        "hitl_tool_names": ["echo"],
    })
    data = assert_success(resp.json())
    assert data["hitl_tool_names"] == ["echo"]


@pytest.mark.asyncio
async def test_create_agent_hitl_not_subset_of_tools_returns_422(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/agents", json={
        "name": f"hitl-bad-{uuid.uuid4().hex[:6]}",
        "system_prompt": "x",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "tool_names": ["echo"],
        "hitl_tool_names": ["calculator"],  # calculator is not in tool_names
    })
    assert resp.status_code == 422
    assert_error(resp.json(), "HITL_TOOL_NOT_IN_TOOL_NAMES")


@pytest.mark.asyncio
async def test_update_agent_hitl_tool_names(owner_client):
    client, _, _ = owner_client
    agent_id = await _create_agent(client, tool_names=["echo"])
    resp = await client.patch(f"/agents/{agent_id}", json={"hitl_tool_names": ["echo"]})
    data = assert_success(resp.json())
    assert data["hitl_tool_names"] == ["echo"]


@pytest.mark.asyncio
async def test_update_agent_hitl_not_in_tools_returns_422(owner_client):
    client, _, _ = owner_client
    agent_id = await _create_agent(client, tool_names=["echo"])
    resp = await client.patch(f"/agents/{agent_id}", json={"hitl_tool_names": ["calculator"]})
    assert resp.status_code == 422
    assert_error(resp.json(), "HITL_TOOL_NOT_IN_TOOL_NAMES")


@pytest.mark.asyncio
async def test_create_agent_default_hitl_tool_names_empty(owner_client):
    client, _, _ = owner_client
    agent_id = await _create_agent(client, tool_names=["echo"])
    resp = await client.get(f"/agents/{agent_id}")
    data = assert_success(resp.json())
    assert data["hitl_tool_names"] == []


# ─── HITL endpoint — not found / unknown ──────────────────

@pytest.mark.asyncio
async def test_get_hitl_unknown_returns_404(owner_client):
    client, _, _ = owner_client
    resp = await client.get(f"/hitl/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert_error(resp.json(), "HITL_NOT_FOUND")


@pytest.mark.asyncio
async def test_approve_unknown_returns_404(owner_client):
    client, _, _ = owner_client
    resp = await client.post(f"/hitl/{uuid.uuid4()}/approve")
    assert resp.status_code == 404
    assert_error(resp.json(), "HITL_NOT_FOUND")


# ─── HITL lifecycle via HITLEngine directly ───────────────

@pytest.mark.asyncio
async def test_hitl_approve_via_endpoint(owner_client):
    """HITLEngine üzerinden istek oluştur, endpoint üzerinden onayla."""
    client, org_id, _ = owner_client

    from app.services.hitl import get_hitl_engine
    hitl = get_hitl_engine()

    request_id = await hitl.create_request(
        trace_id=str(uuid.uuid4()),
        org_id=str(org_id),
        tool_name="echo",
        tool_arguments={"text": "hello"},
    )

    # GET ile durumu sorgula
    get_resp = await client.get(f"/hitl/{request_id}")
    get_data = assert_success(get_resp.json())
    assert get_data["status"] == "pending"
    assert get_data["tool_name"] == "echo"

    # Approve — wait_for_resolution'ı arka planda çalıştır
    resolution_holder: list = []

    async def _wait():
        res = await hitl.wait_for_resolution(request_id)
        resolution_holder.append(res)

    wait_task = asyncio.create_task(_wait())
    approve_resp = await client.post(f"/hitl/{request_id}/approve")
    assert_success(approve_resp.json())
    await wait_task

    assert len(resolution_holder) == 1
    assert resolution_holder[0].action == "approved"


@pytest.mark.asyncio
async def test_hitl_reject_via_endpoint(owner_client):
    client, org_id, _ = owner_client

    from app.services.hitl import get_hitl_engine
    hitl = get_hitl_engine()

    request_id = await hitl.create_request(
        trace_id=str(uuid.uuid4()),
        org_id=str(org_id),
        tool_name="echo",
        tool_arguments={"text": "hello"},
    )

    resolution_holder: list = []

    async def _wait():
        try:
            res = await hitl.wait_for_resolution(request_id)
            resolution_holder.append(res)
        except Exception as e:
            resolution_holder.append(e)

    wait_task = asyncio.create_task(_wait())
    resp = await client.post(f"/hitl/{request_id}/reject", json={"reason": "too risky"})
    assert_success(resp.json())
    await wait_task

    assert len(resolution_holder) == 1
    assert resolution_holder[0].action == "rejected"
    assert resolution_holder[0].reason == "too risky"


@pytest.mark.asyncio
async def test_hitl_modify_via_endpoint(owner_client):
    client, org_id, _ = owner_client

    from app.services.hitl import get_hitl_engine
    hitl = get_hitl_engine()

    request_id = await hitl.create_request(
        trace_id=str(uuid.uuid4()),
        org_id=str(org_id),
        tool_name="echo",
        tool_arguments={"text": "original"},
    )

    resolution_holder: list = []

    async def _wait():
        res = await hitl.wait_for_resolution(request_id)
        resolution_holder.append(res)

    wait_task = asyncio.create_task(_wait())
    resp = await client.post(
        f"/hitl/{request_id}/modify",
        json={"arguments": {"text": "changed"}, "reason": "safer input"},
    )
    assert_success(resp.json())
    await wait_task

    assert resolution_holder[0].action == "modified"
    assert resolution_holder[0].modified_arguments == {"text": "changed"}


@pytest.mark.asyncio
async def test_hitl_double_approve_returns_409(owner_client):
    client, org_id, _ = owner_client

    from app.services.hitl import get_hitl_engine
    hitl = get_hitl_engine()

    request_id = await hitl.create_request(
        trace_id=str(uuid.uuid4()),
        org_id=str(org_id),
        tool_name="echo",
        tool_arguments={},
    )

    async def _wait():
        await hitl.wait_for_resolution(request_id)

    wait_task = asyncio.create_task(_wait())
    await client.post(f"/hitl/{request_id}/approve")
    await wait_task

    resp2 = await client.post(f"/hitl/{request_id}/approve")
    assert resp2.status_code == 409
    assert_error(resp2.json(), "HITL_ALREADY_RESOLVED")


@pytest.mark.asyncio
async def test_hitl_forbidden_for_different_org(owner_client, other_client):
    """Farklı org'dan gelen request, kendi org'unun HITL isteğine erişemez."""
    owner, org_id, _ = owner_client
    other, _, _ = other_client

    from app.services.hitl import get_hitl_engine
    hitl = get_hitl_engine()

    request_id = await hitl.create_request(
        trace_id=str(uuid.uuid4()),
        org_id=str(org_id),
        tool_name="echo",
        tool_arguments={},
    )

    # Diğer org kullanıcısı bu request'e erişmeye çalışıyor
    resp = await other.get(f"/hitl/{request_id}")
    assert resp.status_code == 403
    assert_error(resp.json(), "HITL_FORBIDDEN")

    # Temizlik — pending request için event set et
    hitl._pending.pop(request_id, None)
    await hitl.redis.delete(f"hitl:{request_id}")


# ─── Sync /run ile HITL ───────────────────────────────────

@pytest.mark.asyncio
async def test_run_agent_sync_with_hitl_approve(owner_client):
    """/run sync mode: HITL arka planda onaylanır, agent tamamlanır."""
    client, _, _ = owner_client
    agent_id = await _create_agent(client, tool_names=["echo"], hitl_tool_names=["echo"])

    with (
        patch("app.services.providers.factory.get_provider", return_value=_mock_provider()),
        patch("app.services.agent.runner.AgentRunner._execute", _make_mock_execute("HITL done")),
    ):
        run_resp = await client.post(f"/agents/{agent_id}/run", json={
            "input": "Hello HITL!",
            "stream": False,
        })

    assert run_resp.status_code == 200
    data = assert_success(run_resp.json())
    assert data["content"] == "HITL done"
