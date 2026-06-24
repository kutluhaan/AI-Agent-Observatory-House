"""loop it.4 — Bildirim kanalı CRUD + güvenlik (URL ham dönmez)."""
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
    email = f"notify-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client


@pytest.mark.asyncio
async def test_channel_crud_and_url_never_returned(owner_client):
    client = owner_client
    body = {"name": "slack-alerts", "url": "https://hooks.slack.com/services/XXX/YYY/ZZZ"}
    created = assert_success((await client.post("/notification-channels", json=body)).json())
    assert created["name"] == "slack-alerts" and created["channel_type"] == "webhook"
    assert "url" not in created and "encrypted_url" not in created  # ham URL asla dönmez

    listed = assert_success((await client.get("/notification-channels")).json())
    assert any(c["id"] == created["id"] for c in listed)

    # isim çakışması
    dup = await client.post("/notification-channels", json=body)
    assert dup.status_code == 409

    # sil
    d = await client.delete(f"/notification-channels/{created['id']}")
    assert d.status_code == 204
    listed2 = assert_success((await client.get("/notification-channels")).json())
    assert all(c["id"] != created["id"] for c in listed2)


@pytest.mark.asyncio
async def test_channel_test_send(owner_client):
    client = owner_client
    created = assert_success((await client.post("/notification-channels",
        json={"name": "wh", "url": "https://example.com/webhook"})).json())
    # webhook çağrısını mockla → başarılı
    with patch("app.api.v1.notification_channels.send_webhook", new=AsyncMock(return_value=(True, "ok"))):
        r = assert_success((await client.post(f"/notification-channels/{created['id']}/test")).json())
        assert r["ok"] is True
    # başarısız webhook → 502
    with patch("app.api.v1.notification_channels.send_webhook", new=AsyncMock(return_value=(False, "boom"))):
        bad = await client.post(f"/notification-channels/{created['id']}/test")
        assert bad.status_code == 502
        assert_error(bad.json(), "CHANNEL_TEST_FAILED")


@pytest.mark.asyncio
async def test_test_unknown_channel_404(owner_client):
    client = owner_client
    r = await client.post(f"/notification-channels/{uuid.uuid4()}/test")
    assert r.status_code == 404
