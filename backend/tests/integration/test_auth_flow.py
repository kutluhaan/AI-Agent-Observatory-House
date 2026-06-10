"""
M3 Auth integration — register → verify → login → /me → logout.

Gerçek PostgreSQL + Redis + JWT (.env) gerekir.
Docker backend container içinde çalıştır:

    docker compose -f docker-compose.dev.yml exec backend \\
        pytest tests/integration/test_auth_flow.py -v -m integration
"""
from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
)


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


@pytest.mark.integration
async def test_me_without_cookie_returns_401(client: AsyncClient):
    _require_db()
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert_error(response.json(), "INVALID_TOKEN")


@pytest.mark.integration
async def test_register_login_me_logout_full_flow(client: AsyncClient, auth_user: dict):
    _require_db()
    email = auth_user["email"]
    password = auth_user["password"]

    user_id = await register_and_verify(
        client,
        email=email,
        password=password,
        full_name=auth_user["full_name"],
    )

    pre_login = await client.post(
        "/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert pre_login.status_code == 401

    await login_user(client, email=email, password=password)

    me = await client.get("/auth/me")
    assert me.status_code == 200
    me_data = assert_success(me.json())
    assert me_data["id"] == user_id
    assert me_data["email"] == email
    assert me_data["full_name"] == auth_user["full_name"]
    assert me_data["is_verified"] is True
    assert me_data["organizations"] == []

    logout = await client.post("/auth/logout")
    assert logout.status_code == 200
    assert_success(logout.json())

    me_after = await client.get("/auth/me")
    assert me_after.status_code == 401
    assert_error(me_after.json(), "INVALID_TOKEN")


@pytest.mark.integration
async def test_register_login_requires_verification(client: AsyncClient, auth_user: dict):
    _require_db()
    from unittest.mock import patch

    captured: list[str] = []

    async def _capture(_to: str, raw: str) -> bool:
        captured.append(raw)
        return True

    with patch("app.api.v1.auth.send_verification_email", _capture):
        reg = await client.post(
            "/auth/register",
            json={
                "email": auth_user["email"],
                "password": auth_user["password"],
                "full_name": auth_user["full_name"],
            },
        )
    assert reg.status_code == 201

    pre_login = await client.post(
        "/auth/login",
        json={"email": auth_user["email"], "password": auth_user["password"]},
    )
    assert pre_login.status_code == 403
    assert_error(pre_login.json(), "EMAIL_NOT_VERIFIED")

    verify = await client.post("/auth/verify-email", json={"token": captured[0]})
    assert verify.status_code == 200


@pytest.mark.integration
async def test_register_duplicate_email_returns_409(client: AsyncClient, auth_user: dict):
    _require_db()
    payload = {
        "email": auth_user["email"],
        "password": auth_user["password"],
        "full_name": auth_user["full_name"],
    }
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409
    assert_error(second.json(), "EMAIL_ALREADY_EXISTS")


@pytest.mark.integration
async def test_register_invalid_email_returns_validation_error(client: AsyncClient):
    _require_db()
    response = await client.post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "password": "Test1234!",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert_error(body, "VALIDATION_ERROR")
    fields = body["error"]["details"]["fields"]
    assert any(f["field"] == "email" for f in fields)


@pytest.mark.integration
async def test_login_invalid_credentials_returns_401(client: AsyncClient, auth_user: dict):
    _require_db()
    email = auth_user["email"]
    password = auth_user["password"]

    await register_and_verify(
        client,
        email=email,
        password=password,
        full_name=auth_user["full_name"],
    )

    bad_login = await client.post(
        "/auth/login",
        json={"email": email, "password": "WrongPass1!"},
    )
    assert bad_login.status_code == 401
    assert_error(bad_login.json(), "INVALID_CREDENTIALS")
