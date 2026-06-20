"""
Faz 4 integration — agent bilgi öğeleri (knowledge).

CRUD, always-on enjeksiyon (constitution/rule/instruction/prompt), skill talep-üzerine
okuma (list_skills/read_skill), ve skill/file tool'larının seçilemezliği.
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.services.agent import knowledge_store
from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
)

pytestmark = pytest.mark.integration


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


async def _owner_agent(client: AsyncClient) -> str:
    email = f"kn-{uuid.uuid4().hex[:10]}@example.com"
    uid = await register_and_verify(client, email=email, password="Test1234!", full_name="KN Owner")
    org_id, _ = seed_organization(uid, slug=f"kn-{uuid.uuid4().hex[:8]}")
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    agent = assert_success((await client.post("/agents", json={
        "name": f"KN-{uuid.uuid4().hex[:6]}", "system_prompt": "You are helpful.",
        "provider": "openai", "model": "gpt-4o",
    })).json())
    return agent["id"]


@pytest.mark.asyncio
async def test_knowledge_crud_and_injection(client):
    _require_db()
    agent_id = await _owner_agent(client)
    aid = uuid.UUID(agent_id)

    # Constitution + rule + skill ekle
    c = assert_success((await client.post(f"/agents/{agent_id}/knowledge", json={
        "kind": "constitution", "name": "Tone", "content": "Always be concise and cite sources.",
    })).json())
    await client.post(f"/agents/{agent_id}/knowledge", json={
        "kind": "rule", "name": "No guessing", "content": "Never invent facts.",
    })
    await client.post(f"/agents/{agent_id}/knowledge", json={
        "kind": "skill", "name": "deep-research", "content": "Step 1: search. Step 2: read. Step 3: synthesize.",
    })

    # Listele
    items = assert_success((await client.get(f"/agents/{agent_id}/knowledge")).json())
    kinds = {i["kind"] for i in items}
    assert {"constitution", "rule", "skill"} <= kinds

    # Always-on enjeksiyon constitution + rule içerir, skill içermez
    async with AsyncSessionLocal() as db:
        always = await knowledge_store.load_always_on(db, aid)
        skills_present = await knowledge_store.has_skills(db, aid)
    assert "Always be concise" in always
    assert "Never invent facts" in always
    assert "Step 1: search" not in always  # skill enjekte edilmez
    assert skills_present is True

    # Skill talep üzerine okunur
    listed = await knowledge_store.list_skills(aid)
    assert "deep-research" in listed
    read = await knowledge_store.read_skill(aid, "deep-research")
    assert "Step 1: search" in read

    # Güncelle + sil
    upd = assert_success((await client.patch(
        f"/agents/{agent_id}/knowledge/{c['id']}", json={"content": "Be brief."},
    )).json())
    assert upd["content"] == "Be brief."

    dell = await client.delete(f"/agents/{agent_id}/knowledge/{c['id']}")
    assert dell.status_code == 204


@pytest.mark.asyncio
async def test_invalid_kind_rejected(client):
    _require_db()
    agent_id = await _owner_agent(client)
    resp = await client.post(f"/agents/{agent_id}/knowledge", json={
        "kind": "nonsense", "name": "x", "content": "y",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_skill_tools_not_selectable(client):
    _require_db()
    await _owner_agent(client)
    tools = assert_success((await client.get("/agents/tools")).json())
    names = {t["name"] for t in tools}
    assert "list_skills" not in names
    assert "read_skill" not in names

    resp = await client.post("/agents", json={
        "name": "x", "system_prompt": "x", "provider": "openai", "model": "gpt-4o",
        "tool_names": ["read_skill"],
    })
    assert resp.status_code == 422
    assert_error(resp.json(), "TOOL_AUTO_MANAGED")
