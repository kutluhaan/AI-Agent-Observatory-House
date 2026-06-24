"""loop it.6 — Prompt versiyonlama: otomatik snapshot + restore + config-değişmedi atlanır."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    assert_success, login_user, register_and_verify, seed_organization,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"pv-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client


async def _agent(client) -> dict:
    return assert_success((await client.post("/agents", json={
        "name": f"pv-{uuid.uuid4().hex[:6]}", "system_prompt": "v1 prompt",
        "provider": "openai", "model": "gpt-4o-mini",
    })).json())


@pytest.mark.asyncio
async def test_auto_snapshot_and_restore(owner_client):
    client = owner_client
    a = await _agent(client)
    aid = a["id"]

    # create → v1
    vl = assert_success((await client.get(f"/agents/{aid}/prompt-versions")).json())
    assert vl["active_version"] == 1 and len(vl["versions"]) == 1
    assert vl["versions"][0]["system_prompt"] == "v1 prompt"

    # config değiştir → v2
    assert_success((await client.patch(f"/agents/{aid}", json={"system_prompt": "v2 prompt"})).json())
    vl = assert_success((await client.get(f"/agents/{aid}/prompt-versions")).json())
    assert vl["active_version"] == 2 and len(vl["versions"]) == 2

    # sadece isim değiştir → YENİ sürüm OLUŞMAZ (config aynı)
    assert_success((await client.patch(f"/agents/{aid}", json={"name": "yeni-isim"})).json())
    vl = assert_success((await client.get(f"/agents/{aid}/prompt-versions")).json())
    assert vl["active_version"] == 2 and len(vl["versions"]) == 2

    # v1'e geri yükle → v3 (config v1'e döner)
    restored = assert_success((await client.post(f"/agents/{aid}/prompt-versions/1/restore")).json())
    assert restored["system_prompt"] == "v1 prompt" and restored["prompt_version"] == 3
    vl = assert_success((await client.get(f"/agents/{aid}/prompt-versions")).json())
    assert vl["active_version"] == 3 and len(vl["versions"]) == 3
    assert "geri yüklendi" in vl["versions"][0]["note"]


@pytest.mark.asyncio
async def test_restore_unknown_version_404(owner_client):
    client = owner_client
    a = await _agent(client)
    r = await client.post(f"/agents/{a['id']}/prompt-versions/99/restore")
    assert r.status_code == 404
