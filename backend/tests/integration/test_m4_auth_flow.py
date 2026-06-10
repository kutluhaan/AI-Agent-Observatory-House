"""
M4 Auth integration — verify-email, resend, refresh, switch-org.

Gerçek PostgreSQL + Redis + JWT (.env) gerekir.
Docker backend container içinde çalıştır:

    docker compose -f docker-compose.dev.yml exec backend \\
        pytest tests/integration/test_m4_auth_flow.py -v -m integration
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import jwt_service
from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
    seed_organization_without_membership,
)


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


@pytest.mark.integration
async def test_verify_email_invalid_token_returns_410(client):
    _require_db()
    response = await client.post(
        "/auth/verify-email",
        json={"token": "invalid-token-that-does-not-exist"},
    )
    assert response.status_code == 410
    assert_error(response.json(), "EMAIL_VERIFICATION_EXPIRED")


@pytest.mark.integration
async def test_resend_verification_always_200(client):
    _require_db()
    for email in ("nonexistent@example.com", f"maybe-{uuid.uuid4().hex[:8]}@example.com"):
        response = await client.post("/auth/resend-verification", json={"email": email})
        assert response.status_code == 200
        assert_success(response.json())


@pytest.mark.integration
async def test_resend_verification_rate_limit(client):
    _require_db()
    email = f"ratelimit-resend-{uuid.uuid4().hex[:8]}@example.com"
    for _ in range(3):
        await client.post("/auth/resend-verification", json={"email": email})

    response = await client.post("/auth/resend-verification", json={"email": email})
    assert response.status_code == 429
    assert_error(response.json(), "RATE_LIMIT_EXCEEDED")


@pytest.mark.integration
async def test_refresh_without_cookie_returns_401(client):
    _require_db()
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert_error(response.json(), "INVALID_TOKEN")


@pytest.mark.integration
async def test_refresh_token_rotation_revokes_old_token(client, auth_user: dict):
    _require_db()
    email = auth_user["email"]
    password = auth_user["password"]

    await register_and_verify(
        client,
        email=email,
        password=password,
        full_name=auth_user["full_name"],
    )
    await login_user(client, email=email, password=password)

    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh

    refresh = await client.post("/auth/refresh")
    assert refresh.status_code == 200
    assert_success(refresh.json())
    assert client.cookies.get("refresh_token") != old_refresh

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as stale_client:
        stale_client.cookies.set("refresh_token", old_refresh, path="/auth/refresh")
        retry = await stale_client.post("/auth/refresh")

    assert retry.status_code == 401
    assert_error(retry.json(), "REFRESH_TOKEN_REVOKED")


@pytest.mark.integration
async def test_switch_org_updates_access_token(client, auth_user: dict):
    _require_db()
    email = auth_user["email"]
    password = auth_user["password"]

    user_id = await register_and_verify(
        client,
        email=email,
        password=password,
        full_name=auth_user["full_name"],
    )
    org_a_id, _ = seed_organization(user_id, slug=f"a-{uuid.uuid4().hex[:8]}")
    org_b_id, org_b_slug = seed_organization(user_id, slug=f"b-{uuid.uuid4().hex[:8]}")

    await login_user(client, email=email, password=password)

    switch = await client.post("/auth/switch-org", json={"org_id": org_b_id})
    assert switch.status_code == 200
    switch_data = assert_success(switch.json())
    assert switch_data["organization"]["id"] == org_b_id
    assert switch_data["organization"]["slug"] == org_b_slug
    assert switch_data["role"] == "owner"

    access_token = client.cookies.get("access_token")
    payload = jwt_service.decode_access_token(access_token)
    assert payload["org_id"] == org_b_id
    assert payload["org_slug"] == org_b_slug
    assert payload["role"] == "owner"

    # org_a hâlâ listede — sadece aktif org değişti
    me = await client.get("/auth/me")
    org_ids = {o["id"] for o in assert_success(me.json())["organizations"]}
    assert org_a_id in org_ids
    assert org_b_id in org_ids


@pytest.mark.integration
async def test_switch_org_not_member_returns_403(client, auth_user: dict):
    _require_db()
    email = auth_user["email"]
    password = auth_user["password"]

    user_id = await register_and_verify(
        client,
        email=email,
        password=password,
        full_name=auth_user["full_name"],
    )
    other_org_id = seed_organization_without_membership(user_id)

    await login_user(client, email=email, password=password)

    response = await client.post("/auth/switch-org", json={"org_id": other_org_id})
    assert response.status_code == 403
    assert_error(response.json(), "NOT_A_MEMBER")


@pytest.mark.integration
async def test_switch_org_unknown_org_returns_404(client, auth_user: dict):
    _require_db()
    email = auth_user["email"]
    password = auth_user["password"]

    await register_and_verify(
        client,
        email=email,
        password=password,
        full_name=auth_user["full_name"],
    )
    await login_user(client, email=email, password=password)

    response = await client.post("/auth/switch-org", json={"org_id": str(uuid.uuid4())})
    assert response.status_code == 404
    assert_error(response.json(), "ORGANIZATION_NOT_FOUND")
