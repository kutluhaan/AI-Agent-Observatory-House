"""
M3 Auth integration — register → login → /me → logout.

Gerçek PostgreSQL + Redis + JWT (.env) gerekir.
Docker backend container içinde çalıştır:

    docker compose -f docker-compose.dev.yml exec backend \
        pytest tests/integration/test_auth_flow.py -v -m integration
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, text


# ─── Helpers ──────────────────────────────────────────────


def _sync_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set — run inside docker backend container")
    return url.replace("postgresql+asyncpg", "postgresql+psycopg")


def _unique_email() -> str:
    return f"m3-test-{uuid.uuid4().hex[:12]}@example.com"


def _set_user_verified(user_id: str) -> None:
    engine = create_engine(_sync_database_url())
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_verified = true WHERE id = :id"),
            {"id": user_id},
        )


def _assert_error(body: dict, code: str) -> None:
    assert body["success"] is False
    assert body["error"]["code"] == code


def _assert_success(body: dict) -> dict:
    assert body["success"] is True
    assert "data" in body
    assert "meta" in body
    return body["data"]

# ─── Tests ────────────────────────────────────────────────


@pytest.mark.integration
async def test_me_without_cookie_returns_401(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401
    _assert_error(response.json(), "INVALID_TOKEN")


@pytest.mark.integration
async def test_register_login_me_logout_full_flow(client: AsyncClient, auth_user: dict):
    email = auth_user["email"]
    password = auth_user["password"]

    # 1. Register
    reg = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": auth_user["full_name"],
        },
    )
    assert reg.status_code == 201
    reg_data = _assert_success(reg.json())
    assert "user_id" in reg_data
    user_id = reg_data["user_id"]

    # 2. Login before verify → 403
    pre_login = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert pre_login.status_code == 403
    _assert_error(pre_login.json(), "EMAIL_NOT_VERIFIED")

    # 3. Verify user (M4 verify-email yok — test helper)
    _set_user_verified(user_id)

    # 4. Login → cookies
    login = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    login_data = _assert_success(login.json())
    assert login_data["user"]["email"] == email
    assert login_data["user"]["is_verified"] is True
    assert "access_token" in client.cookies

    # 5. /me → 200 (auth-spec format)
    me = await client.get("/auth/me")
    assert me.status_code == 200
    me_data = _assert_success(me.json())
    assert me_data["id"] == user_id
    assert me_data["email"] == email
    assert me_data["full_name"] == auth_user["full_name"]
    assert me_data["is_verified"] is True
    assert me_data["organizations"] == []

    # 6. Logout
    logout = await client.post("/auth/logout")
    assert logout.status_code == 200
    _assert_success(logout.json())

    # 7. /me after logout → 401 (blacklist + cookie cleared)
    me_after = await client.get("/auth/me")
    assert me_after.status_code == 401
    _assert_error(me_after.json(), "INVALID_TOKEN")


@pytest.mark.integration
async def test_register_duplicate_email_returns_409(client: AsyncClient, auth_user: dict):
    payload = {
        "email": auth_user["email"],
        "password": auth_user["password"],
        "full_name": auth_user["full_name"],
    }
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409
    _assert_error(second.json(), "EMAIL_ALREADY_EXISTS")


@pytest.mark.integration
async def test_register_invalid_email_returns_validation_error(client: AsyncClient):
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
    _assert_error(body, "VALIDATION_ERROR")
    fields = body["error"]["details"]["fields"]
    assert any(f["field"] == "email" for f in fields)


@pytest.mark.integration
async def test_login_invalid_credentials_returns_401(client: AsyncClient, auth_user: dict):
    email = auth_user["email"]
    password = auth_user["password"]

    reg = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": auth_user["full_name"],
        },
    )
    assert reg.status_code == 201
    _set_user_verified(_assert_success(reg.json())["user_id"])

    bad_login = await client.post(
        "/auth/login",
        json={"email": email, "password": "WrongPass1!"},
    )
    assert bad_login.status_code == 401
    _assert_error(bad_login.json(), "INVALID_CREDENTIALS")