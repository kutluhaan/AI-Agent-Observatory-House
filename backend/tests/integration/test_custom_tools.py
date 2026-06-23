"""B1 (#1) — custom tool CRUD + test integration."""
from __future__ import annotations

import uuid

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


@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"ct-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


def _payload(name=None):
    return {
        "name": name or f"tool_{uuid.uuid4().hex[:6]}",
        "description": "Hava durumu",
        "method": "GET",
        "url": "http://api.example/{city}/weather",
        "headers": {"X-Api-Key": "secret-123"},
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    }


@pytest.mark.asyncio
async def test_create_lists_and_hides_headers(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/custom-tools", json=_payload("get_weather"))
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["name"] == "get_weather"
    assert data["header_names"] == ["X-Api-Key"]   # yalnız anahtar adı
    assert "secret-123" not in str(data)            # değer gizli

    listed = assert_success((await client.get("/custom-tools")).json())
    assert any(t["id"] == data["id"] for t in listed)


@pytest.mark.asyncio
async def test_reserved_name_422(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/custom-tools", json={**_payload(), "name": "web_search"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_name_conflict_409(owner_client):
    client, _, _ = owner_client
    name = f"dup_{uuid.uuid4().hex[:6]}"
    await client.post("/custom-tools", json=_payload(name))
    resp = await client.post("/custom-tools", json=_payload(name))
    assert resp.status_code == 409
    assert_error(resp.json(), "CUSTOM_TOOL_NAME_CONFLICT")


@pytest.mark.asyncio
async def test_update_and_delete(owner_client):
    client, _, _ = owner_client
    tid = assert_success((await client.post("/custom-tools", json=_payload())).json())["id"]
    upd = assert_success((await client.patch(f"/custom-tools/{tid}", json={"description": "yeni"})).json())
    assert upd["description"] == "yeni"
    assert (await client.delete(f"/custom-tools/{tid}")).status_code == 204
    assert all(t["id"] != tid for t in assert_success((await client.get("/custom-tools")).json()))


@pytest.mark.asyncio
async def test_test_endpoint_unreachable_returns_error(owner_client):
    client, _, _ = owner_client
    tid = assert_success((await client.post("/custom-tools", json={
        **_payload(), "url": "http://127.0.0.1:1/x",
    })).json())["id"]
    res = assert_success((await client.post(f"/custom-tools/{tid}/test", json={"arguments": {"city": "x"}})).json())
    assert "error" in res["result"].lower()


@pytest.mark.asyncio
async def test_create_agent_with_custom_tool(owner_client):
    client, _, _ = owner_client
    tid = assert_success((await client.post("/custom-tools", json=_payload())).json())["id"]
    resp = await client.post("/agents", json={
        "name": f"ct-agent-{uuid.uuid4().hex[:6]}", "system_prompt": "x",
        "provider": "openai", "model": "gpt-4o-mini", "custom_tool_ids": [tid],
    })
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert str(data["custom_tool_ids"][0]) == tid
