"""F8 — Team CRUD + run integration."""
from __future__ import annotations

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


@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"team-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


async def _agent(client) -> str:
    resp = await client.post("/agents", json={
        "name": f"a-{uuid.uuid4().hex[:6]}", "system_prompt": "x",
        "provider": "openai", "model": "gpt-4o-mini",
    })
    return assert_success(resp.json())["id"]


async def _team(client, *, with_coordinator=True) -> dict:
    coord = await _agent(client)
    worker = await _agent(client)
    members = [{"agent_id": worker, "role": "worker", "role_prompt": "work"}]
    if with_coordinator:
        members.insert(0, {"agent_id": coord, "role": "coordinator", "role_prompt": "lead"})
    return {"name": f"t-{uuid.uuid4().hex[:6]}", "members": members}


@pytest.mark.asyncio
async def test_roles_catalog(owner_client):
    client, _, _ = owner_client
    roles = assert_success((await client.get("/teams/roles")).json())
    keys = {r["role"] for r in roles}
    assert "coordinator" in keys and "evaluator" in keys
    assert all(r["default_prompt"] for r in roles)


@pytest.mark.asyncio
async def test_create_team_requires_coordinator(owner_client):
    client, _, _ = owner_client
    body = await _team(client, with_coordinator=False)
    resp = await client.post("/teams", json=body)
    assert resp.status_code == 422  # tam 1 coordinator şart


@pytest.mark.asyncio
async def test_create_list_get_team(owner_client):
    client, _, _ = owner_client
    body = await _team(client)
    created = assert_success((await client.post("/teams", json=body)).json())
    assert len(created["members"]) == 2
    assert any(m["role"] == "coordinator" for m in created["members"])
    assert created["members"][0]["agent_name"]

    listed = assert_success((await client.get("/teams")).json())
    assert any(t["id"] == created["id"] for t in listed)

    got = assert_success((await client.get(f"/teams/{created['id']}")).json())
    assert got["id"] == created["id"]


@pytest.mark.asyncio
async def test_delete_team(owner_client):
    client, _, _ = owner_client
    tid = assert_success((await client.post("/teams", json=await _team(client))).json())["id"]
    assert (await client.delete(f"/teams/{tid}")).status_code == 204
    assert (await client.get(f"/teams/{tid}")).status_code == 404


@pytest.mark.asyncio
async def test_run_team_creates_pending_run(owner_client):
    client, _, _ = owner_client
    tid = assert_success((await client.post("/teams", json=await _team(client))).json())["id"]
    with patch("app.services.team.runner.TeamRunner.run", new_callable=AsyncMock):
        resp = await client.post(f"/teams/{tid}/run", json={"input": "Build X"})
    assert resp.status_code == 202
    run = assert_success(resp.json())
    assert run["status"] == "pending"
    assert run["input"] == "Build X"

    # run detayı (mesaj timeline'ı boş ama erişilebilir)
    detail = assert_success((await client.get(f"/team-runs/{run['id']}")).json())
    assert detail["run"]["id"] == run["id"]
    assert isinstance(detail["messages"], list)


@pytest.mark.asyncio
async def test_run_detail_not_found(owner_client):
    client, _, _ = owner_client
    resp = await client.get(f"/team-runs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert_error(resp.json(), "TEAM_RUN_NOT_FOUND")
