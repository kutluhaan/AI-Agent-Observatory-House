"""G1 — Connections (Gmail OAuth) integration."""
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
    email = f"conn-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


@pytest.mark.asyncio
async def test_list_connections_empty(owner_client):
    client, _, _ = owner_client
    data = assert_success((await client.get("/connections")).json())
    assert data == []


@pytest.mark.asyncio
async def test_authorize_behaviour_matches_config(owner_client):
    """Google yapılandırılmışsa authorize URL döner; değilse 400 GOOGLE_NOT_CONFIGURED.
    (Env'e bağlı; iki durumu da doğru kabul eder.)"""
    from app.services.connections.google_oauth import is_configured
    client, _, _ = owner_client
    resp = await client.post("/connections/google/authorize", json={})
    if is_configured():
        assert resp.status_code == 200
        data = assert_success(resp.json())
        assert data["authorize_url"].startswith("https://accounts.google.com/")
    else:
        assert resp.status_code == 400
        assert_error(resp.json(), "GOOGLE_NOT_CONFIGURED")


@pytest.mark.asyncio
async def test_disconnect_when_none_is_noop(owner_client):
    client, _, _ = owner_client
    resp = await client.delete("/connections/google")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_connections_requires_auth(client: AsyncClient):
    from httpx import ASGITransport, AsyncClient as AC
    from app.main import app
    transport = ASGITransport(app=app)
    async with AC(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/connections")
    assert resp.status_code == 401
