"""
Faz 3 integration — agent izole dosya sistemi + file tool'ları.

file_store round-trip (write/read/mkdir/list/search/move/delete), agent başına
izolasyon, dosya gezgini endpoint'leri, ve file tool'larının seçilemezliği.
Gerçek PostgreSQL gerekir.
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient

from app.services.agent import file_store
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


async def _owner(client: AsyncClient) -> str:
    email = f"fs-{uuid.uuid4().hex[:10]}@example.com"
    uid = await register_and_verify(client, email=email, password="Test1234!", full_name="FS Owner")
    org_id, _ = seed_organization(uid, slug=f"fs-{uuid.uuid4().hex[:8]}")
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return org_id


async def _create_agent(client: AsyncClient, fs: bool = True, tools=None) -> dict:
    resp = await client.post("/agents", json={
        "name": f"FS-{uuid.uuid4().hex[:6]}",
        "system_prompt": "You are helpful.",
        "provider": "openai",
        "model": "gpt-4o",
        "tool_names": tools or [],
        "file_system_enabled": fs,
    })
    return assert_success(resp.json())


@pytest.mark.asyncio
async def test_file_tools_excluded_from_tool_list(client):
    _require_db()
    await _owner(client)
    tools = assert_success((await client.get("/agents/tools")).json())
    names = {t["name"] for t in tools}
    assert "echo" in names
    for ft in ("write_file", "read_file", "move_file"):
        assert ft not in names


@pytest.mark.asyncio
async def test_cannot_manually_select_file_tool(client):
    _require_db()
    await _owner(client)
    resp = await client.post("/agents", json={
        "name": "x", "system_prompt": "x", "provider": "openai", "model": "gpt-4o",
        "tool_names": ["write_file"],
    })
    assert resp.status_code == 422
    assert_error(resp.json(), "TOOL_AUTO_MANAGED")


@pytest.mark.asyncio
async def test_file_store_roundtrip_and_explorer(client):
    _require_db()
    org_id = await _owner(client)
    agent = await _create_agent(client, fs=True)
    aid = uuid.UUID(agent["id"])
    oid = uuid.UUID(org_id)
    assert agent["file_system_enabled"] is True

    assert "Wrote" in await file_store.write_file(aid, oid, "notes/a.md", "hello world")
    assert await file_store.read_file(aid, "notes/a.md") == "hello world"

    await file_store.make_directory(aid, oid, "data")
    listing = await file_store.list_files(aid)
    assert "notes/a.md" in listing and "data" in listing

    assert "notes/a.md" in await file_store.search_files(aid, "hello")

    await file_store.modify_file(aid, "notes/a.md", "world", "there")
    assert await file_store.read_file(aid, "notes/a.md") == "hello there"

    await file_store.move_file(aid, "notes/a.md", "notes/b.md")
    assert await file_store.read_file(aid, "notes/b.md") == "hello there"
    assert "not found" in await file_store.read_file(aid, "notes/a.md")

    await file_store.delete_file(aid, "notes/b.md")
    assert "not found" in await file_store.read_file(aid, "notes/b.md")

    # Dosya gezgini endpoint'leri
    await file_store.write_file(aid, oid, "report.txt", "final report")
    files = assert_success((await client.get(f"/agents/{aid}/files")).json())
    assert "report.txt" in {f["path"] for f in files}
    content = assert_success((await client.get(f"/agents/{aid}/files/content?path=report.txt")).json())
    assert content["content"] == "final report"


@pytest.mark.asyncio
async def test_file_isolation_between_agents(client):
    _require_db()
    org_id = await _owner(client)
    a1 = await _create_agent(client, fs=True)
    a2 = await _create_agent(client, fs=True)
    oid = uuid.UUID(org_id)

    await file_store.write_file(uuid.UUID(a1["id"]), oid, "secret.txt", "a1 data")

    # a2 başka agent'ın dosyasını göremez
    assert "not found" in await file_store.read_file(uuid.UUID(a2["id"]), "secret.txt")
    files2 = assert_success((await client.get(f"/agents/{a2['id']}/files")).json())
    assert all(f["path"] != "secret.txt" for f in files2)
