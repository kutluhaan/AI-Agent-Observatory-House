"""loop it.8 — DB bağlantısı CRUD + canlı /test (uygulamanın kendi DB'sine SELECT 1)."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.integration.auth_helpers import (
    assert_success, login_user, register_and_verify, seed_organization,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"db-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client


@pytest.mark.asyncio
async def test_db_conn_crud_and_live_test(owner_client):
    client = owner_client
    dsn = get_settings().database_url  # uygulamanın kendi DB'si — salt-okunur test

    created = assert_success((await client.post("/db-connections", json={"name": "app-db", "dsn": dsn})).json())
    assert created["db_type"] == "postgres"
    assert "dsn" not in created and "encrypted_dsn" not in created  # ham DSN dönmez

    # canlı bağlantı testi → SELECT 1 gerçekten çalışır
    r = assert_success((await client.post(f"/db-connections/{created['id']}/test")).json())
    assert r["ok"] is True

    listed = assert_success((await client.get("/db-connections")).json())
    assert any(c["id"] == created["id"] for c in listed)

    dup = await client.post("/db-connections", json={"name": "app-db", "dsn": dsn})
    assert dup.status_code == 409

    d = await client.delete(f"/db-connections/{created['id']}")
    assert d.status_code == 204


@pytest.mark.asyncio
async def test_test_unknown_conn_404(owner_client):
    client = owner_client
    r = await client.post(f"/db-connections/{uuid.uuid4()}/test")
    assert r.status_code == 404
