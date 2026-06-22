"""F7.2 — MCP server CRUD + discovery integration."""
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
    email = f"mcp-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


@pytest.mark.asyncio
async def test_create_and_list_mcp_server(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/mcp-servers", json={
        "name": f"srv-{uuid.uuid4().hex[:6]}",
        "url": "http://mcp.example/mcp",
        "api_key": "secret-token",
    })
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["has_api_key"] is True
    assert "secret-token" not in str(data)  # key sızdırılmaz

    listed = assert_success((await client.get("/mcp-servers")).json())
    assert any(s["id"] == data["id"] for s in listed)


@pytest.mark.asyncio
async def test_mcp_name_conflict_409(owner_client):
    client, _, _ = owner_client
    name = f"dup-{uuid.uuid4().hex[:6]}"
    body = {"name": name, "url": "http://mcp.example/mcp"}
    await client.post("/mcp-servers", json=body)
    resp = await client.post("/mcp-servers", json=body)
    assert resp.status_code == 409
    assert_error(resp.json(), "MCP_NAME_CONFLICT")


@pytest.mark.asyncio
async def test_delete_mcp_server(owner_client):
    client, _, _ = owner_client
    sid = assert_success((await client.post("/mcp-servers", json={
        "name": f"del-{uuid.uuid4().hex[:6]}", "url": "http://mcp.example/mcp",
    })).json())["id"]
    resp = await client.delete(f"/mcp-servers/{sid}")
    assert resp.status_code == 204
    listed = assert_success((await client.get("/mcp-servers")).json())
    assert all(s["id"] != sid for s in listed)


@pytest.mark.asyncio
async def test_discover_unreachable_returns_502(owner_client):
    client, _, _ = owner_client
    sid = assert_success((await client.post("/mcp-servers", json={
        "name": f"bad-{uuid.uuid4().hex[:6]}", "url": "http://127.0.0.1:1/mcp",
    })).json())["id"]
    resp = await client.get(f"/mcp-servers/{sid}/tools")
    assert resp.status_code == 502
    assert_error(resp.json(), "MCP_CONNECT_FAILED")


@pytest.mark.asyncio
async def test_create_agent_with_mcp_tools(owner_client):
    client, _, _ = owner_client
    sid = assert_success((await client.post("/mcp-servers", json={
        "name": f"srv2-{uuid.uuid4().hex[:6]}", "url": "http://mcp.example/mcp",
    })).json())["id"]

    resp = await client.post("/agents", json={
        "name": f"mcp-agent-{uuid.uuid4().hex[:6]}",
        "system_prompt": "x",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mcp_tools": [{"server_id": sid, "tool_name": "search",
                       "description": "Web search", "input_schema": {"type": "object"}}],
    })
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["mcp_tools"][0]["tool_name"] == "search"
