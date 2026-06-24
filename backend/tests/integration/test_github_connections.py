"""loop it.9 — GitHub bağlantısı CRUD + güvenlik (token ham dönmez) + test (mock)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    assert_error, assert_success, login_user, register_and_verify, seed_organization,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"gh-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client


@pytest.mark.asyncio
async def test_github_crud_and_token_never_returned(owner_client):
    client = owner_client
    created = assert_success((await client.post("/github-connections",
        json={"name": "default", "token": "ghp_xxxxxxxxxxxxxxxx"})).json())
    assert created["name"] == "default"
    assert "token" not in created and "encrypted_token" not in created  # ham token dönmez

    listed = assert_success((await client.get("/github-connections")).json())
    assert any(c["id"] == created["id"] for c in listed)

    dup = await client.post("/github-connections", json={"name": "default", "token": "ghp_yyyy"})
    assert dup.status_code == 409

    d = await client.delete(f"/github-connections/{created['id']}")
    assert d.status_code == 204


@pytest.mark.asyncio
async def test_github_test_endpoint(owner_client):
    client = owner_client
    created = assert_success((await client.post("/github-connections",
        json={"name": "t", "token": "ghp_zzzzzzzz"})).json())
    with patch("app.api.v1.github_connections._gh", new=AsyncMock(return_value=(200, {"login": "octocat"}))):
        r = assert_success((await client.post(f"/github-connections/{created['id']}/test")).json())
        assert r["ok"] is True and r["login"] == "octocat"
    with patch("app.api.v1.github_connections._gh", new=AsyncMock(return_value=(401, {"message": "Bad credentials"}))):
        bad = await client.post(f"/github-connections/{created['id']}/test")
        assert bad.status_code == 502
        assert_error(bad.json(), "GITHUB_CONN_TEST_FAILED")
