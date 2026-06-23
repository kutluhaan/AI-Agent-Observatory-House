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


@pytest.mark.asyncio
async def test_team_budgets_create_and_patch(owner_client):
    """B3+: ekip promptu + bütçeler create/patch + varsayılanlar + sınır."""
    client, _, _ = owner_client
    body = await _team(client)
    body |= {"shared_instructions": "Kısa çalış.", "max_delegations": 5, "run_timeout_seconds": 300}
    t = assert_success((await client.post("/teams", json=body)).json())
    assert t["shared_instructions"] == "Kısa çalış." and t["max_delegations"] == 5 and t["run_timeout_seconds"] == 300

    t2 = assert_success((await client.post("/teams", json=await _team(client))).json())
    assert t2["max_delegations"] == 12 and t2["run_timeout_seconds"] == 600  # varsayılanlar

    upd = assert_success((await client.patch(f"/teams/{t['id']}", json={"max_delegations": 8, "shared_instructions": ""})).json())
    assert upd["max_delegations"] == 8 and upd["shared_instructions"] is None

    bad = await client.patch(f"/teams/{t['id']}", json={"max_delegations": 999})
    assert bad.status_code == 422  # sınır ihlali


@pytest.mark.asyncio
async def test_budget_awareness_injected_into_prompt(owner_client):
    """Bütçe ajanın prompt'una dinamik enjekte edilir — ajan limiti BİLEREK çalışır."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.database import AsyncSessionLocal
    from app.models.team import Team, TeamMember
    from app.services.team.executor import build_member_runner

    client, _, _ = owner_client
    body = await _team(client)
    body |= {"max_delegations": 7}
    tid = assert_success((await client.post("/teams", json=body)).json())["id"]

    async with AsyncSessionLocal() as db:
        team = (await db.execute(
            select(Team).where(Team.id == uuid.UUID(tid))
            .options(selectinload(Team.members).selectinload(TeamMember.agent))
        )).scalar_one()
        coord = next(m for m in team.members if m.role == "coordinator")
        worker = next(m for m in team.members if m.role == "worker")
        rc = await build_member_runner(db, None, coord, list(team.members), org_id=team.organization_id, team_id=team.id, team_run_id=team.id)
        rw = await build_member_runner(db, None, worker, list(team.members), org_id=team.organization_id, team_id=team.id, team_run_id=team.id)

    cp = rc.config.system_prompt
    assert "ÇALIŞMA BÜTÇEN" in cp and "EN FAZLA 7" in cp and "CEVAP DÖNDÜRMEZ" in cp  # coordinator delege limitini bilir
    assert "ÇALIŞMA BÜTÇEN" in rw.config.system_prompt  # üye de kendi adım/süre bütçesini bilir


@pytest.mark.asyncio
async def test_team_chat_conversation(owner_client):
    """B3: aynı conversation_id ile çok-turlu; listeleme + tur getirme."""
    client, _, _ = owner_client
    tid = assert_success((await client.post("/teams", json=await _team(client))).json())["id"]
    with patch("app.services.team.runner.TeamRunner.run", new_callable=AsyncMock):
        r1 = assert_success((await client.post(f"/teams/{tid}/run", json={"input": "ilk soru"})).json())
        conv = r1["conversation_id"]
        assert conv  # her run bir sohbete ait
        r2 = assert_success((await client.post(f"/teams/{tid}/run", json={"input": "ikinci soru", "conversation_id": conv})).json())
        assert r2["conversation_id"] == conv

    convs = assert_success((await client.get(f"/teams/{tid}/conversations")).json())
    mine = next((c for c in convs if c["conversation_id"] == conv), None)
    assert mine and mine["turns"] == 2 and mine["first_input"] == "ilk soru"

    runs = assert_success((await client.get(f"/teams/{tid}/conversations/{conv}")).json())
    assert len(runs) == 2
    assert [r["input"] for r in runs] == ["ilk soru", "ikinci soru"]  # eski → yeni
