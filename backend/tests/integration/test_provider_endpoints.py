"""
M7 integration — provider credential CRUD + health check + RBAC.

Gerçek PostgreSQL + Redis + JWT (.env) gerekir. M3/M4/M5 ile aynı harness.
Docker backend container içinde çalıştır:

    docker compose -f docker-compose.dev.yml exec backend \\
        pytest tests/integration/test_provider_endpoints.py -v -m integration
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    add_member,
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
)


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


async def _new_verified_user(client: AsyncClient, prefix: str = "prov") -> tuple[str, str, str]:
    """Register+verify edilmiş kullanıcı. (user_id, email, password) döner."""
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    password = "Test1234!"
    user_id = await register_and_verify(
        client, email=email, password=password, full_name="M7 User"
    )
    return user_id, email, password


async def _owner_in_org(client: AsyncClient) -> tuple[str, str]:
    """Owner kullanıcı + org oluştur, login + switch-org yap. (user_id, org_id) döner."""
    user_id, email, password = await _new_verified_user(client, "owner")
    org_id = seed_organization(user_id, slug=f"prov-{uuid.uuid4().hex[:8]}")[0]
    await login_user(client, email=email, password=password)
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return user_id, org_id


async def _member_in_org(client: AsyncClient, org_id: str) -> None:
    """Org'a member rolüyle yeni kullanıcı ekle, login + switch-org yap."""
    member_id, email, password = await _new_verified_user(client, "member")
    add_member(org_id, member_id, "member")
    await login_user(client, email=email, password=password)
    await client.post("/auth/switch-org", json={"org_id": org_id})


# ─── Create Credential ────────────────────────────────────

@pytest.mark.integration
async def test_admin_can_set_openai_credential(client):
    _require_db()
    await _owner_in_org(client)

    resp = await client.post(
        "/providers", json={"provider": "openai", "api_key": "sk-test-key-12345"}
    )
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["provider"] == "openai"
    assert data["is_configured"] is True


@pytest.mark.integration
async def test_member_cannot_set_credential(client):
    _require_db()
    _, org_id = await _owner_in_org(client)
    await _member_in_org(client, org_id)

    resp = await client.post(
        "/providers", json={"provider": "openai", "api_key": "sk-test"}
    )
    assert resp.status_code == 403
    assert_error(resp.json(), "INSUFFICIENT_PERMISSIONS")


@pytest.mark.integration
async def test_set_ollama_requires_base_url(client):
    _require_db()
    await _owner_in_org(client)

    resp = await client.post("/providers", json={"provider": "ollama"})
    assert resp.status_code == 422
    assert_error(resp.json(), "VALIDATION_ERROR")


@pytest.mark.integration
async def test_set_ollama_with_base_url_succeeds(client):
    _require_db()
    await _owner_in_org(client)

    resp = await client.post(
        "/providers", json={"provider": "ollama", "base_url": "http://localhost:11434"}
    )
    assert resp.status_code == 201
    assert assert_success(resp.json())["base_url"] == "http://localhost:11434"


# ─── Custom (self-hosted OpenAI-compatible) provider — F3 ──

@pytest.mark.integration
async def test_set_custom_requires_base_url(client):
    _require_db()
    await _owner_in_org(client)
    resp = await client.post("/providers", json={"provider": "custom"})
    assert resp.status_code == 422
    assert_error(resp.json(), "VALIDATION_ERROR")


@pytest.mark.integration
async def test_set_custom_with_base_url_succeeds_keyless(client):
    _require_db()
    await _owner_in_org(client)
    resp = await client.post(
        "/providers", json={"provider": "custom", "base_url": "http://gpu-server:8000/v1"}
    )
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["provider"] == "custom"
    assert data["base_url"] == "http://gpu-server:8000/v1"


@pytest.mark.integration
async def test_create_agent_with_custom_provider(client):
    _require_db()
    await _owner_in_org(client)
    resp = await client.post("/agents", json={
        "name": f"custom-{uuid.uuid4().hex[:6]}",
        "system_prompt": "You are helpful.",
        "provider": "custom",
        "model": "gpt-oss-20b",
    })
    assert resp.status_code == 201
    assert assert_success(resp.json())["provider"] == "custom"


@pytest.mark.integration
async def test_invalid_provider_name_rejected(client):
    _require_db()
    await _owner_in_org(client)

    resp = await client.post(
        "/providers", json={"provider": "made-up", "api_key": "sk-test"}
    )
    assert resp.status_code == 422


# ─── List Credentials ─────────────────────────────────────

@pytest.mark.integration
async def test_list_credentials_masks_key(client):
    _require_db()
    await _owner_in_org(client)
    await client.post(
        "/providers", json={"provider": "openai", "api_key": "sk-real-secret-key"}
    )

    resp = await client.get("/providers")
    assert resp.status_code == 200
    providers = assert_success(resp.json())

    openai_entry = next(p for p in providers if p["provider"] == "openai")
    assert openai_entry["is_configured"] is True
    assert openai_entry["masked_key"] is not None
    assert "sk-real-secret-key" not in str(openai_entry["masked_key"])


@pytest.mark.integration
async def test_list_credentials_shows_unconfigured_providers(client):
    _require_db()
    await _owner_in_org(client)

    resp = await client.get("/providers")
    assert resp.status_code == 200
    providers = assert_success(resp.json())
    assert len(providers) == 5  # openai, anthropic, gemini, ollama, custom
    assert all(p["is_configured"] is False for p in providers)


@pytest.mark.integration
async def test_member_can_list_credentials(client):
    _require_db()
    _, org_id = await _owner_in_org(client)
    await _member_in_org(client, org_id)

    resp = await client.get("/providers")
    assert resp.status_code == 200


# ─── Delete Credential ─────────────────────────────────────

@pytest.mark.integration
async def test_delete_credential_success(client):
    _require_db()
    await _owner_in_org(client)
    await client.post(
        "/providers", json={"provider": "anthropic", "api_key": "sk-ant-test"}
    )

    resp = await client.delete("/providers/anthropic")
    assert resp.status_code == 204

    list_resp = await client.get("/providers")
    entry = next(p for p in assert_success(list_resp.json()) if p["provider"] == "anthropic")
    assert entry["is_configured"] is False


@pytest.mark.integration
async def test_delete_nonexistent_credential_404(client):
    _require_db()
    await _owner_in_org(client)

    resp = await client.delete("/providers/openai")
    assert resp.status_code == 404
    assert_error(resp.json(), "PROVIDER_NOT_CONFIGURED")


@pytest.mark.integration
async def test_member_cannot_delete_credential(client):
    _require_db()
    _, org_id = await _owner_in_org(client)
    await _member_in_org(client, org_id)

    resp = await client.delete("/providers/openai")
    assert resp.status_code == 403


# ─── Health Check ─────────────────────────────────────────

@pytest.mark.integration
async def test_health_check_unhealthy_without_credential(client, monkeypatch):
    _require_db()
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "")
    await _owner_in_org(client)

    resp = await client.get("/providers/openai/health")
    assert resp.status_code == 404
    assert_error(resp.json(), "PROVIDER_NOT_CONFIGURED")


@pytest.mark.integration
async def test_health_check_with_mocked_provider(client, monkeypatch):
    _require_db()
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "sk-test")
    await _owner_in_org(client)

    with patch(
        "app.services.providers.openai_provider.OpenAIProvider.health_check",
        new=AsyncMock(return_value=True),
    ):
        resp = await client.get("/providers/openai/health")
        assert resp.status_code == 200
        assert assert_success(resp.json())["healthy"] is True
