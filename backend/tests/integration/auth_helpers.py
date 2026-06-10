"""Paylaşılan auth integration test yardımcıları."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import create_engine, text


def sync_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set — run inside docker backend container")
    return url.replace("postgresql+asyncpg", "postgresql+psycopg")


def assert_error(body: dict, code: str) -> None:
    assert body["success"] is False
    assert body["error"]["code"] == code


def assert_success(body: dict) -> dict:
    assert body["success"] is True
    assert "data" in body
    assert "meta" in body
    return body["data"]


async def register_and_verify(
    client: AsyncClient,
    *,
    email: str,
    password: str,
    full_name: str,
) -> str:
    """Register → verify-email; user_id döner."""
    captured: list[str] = []

    async def _capture(_to_email: str, raw_token: str) -> bool:
        captured.append(raw_token)
        return True

    with patch("app.api.v1.auth.send_verification_email", _capture):
        reg = await client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )
    assert reg.status_code == 201
    user_id = assert_success(reg.json())["user_id"]

    verify = await client.post("/auth/verify-email", json={"token": captured[0]})
    assert verify.status_code == 200

    return user_id


async def login_user(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> None:
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200


def seed_organization(owner_user_id: str, slug: str | None = None) -> tuple[str, str]:
    """Kullanıcıyı owner yaparak org oluşturur. (org_id, slug) döner."""
    org_id = str(uuid.uuid4())
    org_slug = slug or f"org-{uuid.uuid4().hex[:10]}"
    engine = create_engine(sync_database_url())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO organizations (id, name, slug, plan, is_active, created_by)
                VALUES (:id, :name, :slug, 'free', true, :created_by)
                """
            ),
            {
                "id": org_id,
                "name": "Test Org",
                "slug": org_slug,
                "created_by": owner_user_id,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO organization_members (organization_id, user_id, role)
                VALUES (:org_id, :user_id, 'owner')
                """
            ),
            {"org_id": org_id, "user_id": owner_user_id},
        )
    return org_id, org_slug


def seed_organization_without_membership(created_by_user_id: str) -> str:
    """Üyelik olmadan org oluşturur — switch-org NOT_A_MEMBER testleri için."""
    org_id = str(uuid.uuid4())
    org_slug = f"other-{uuid.uuid4().hex[:10]}"
    engine = create_engine(sync_database_url())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO organizations (id, name, slug, plan, is_active, created_by)
                VALUES (:id, :name, :slug, 'free', true, :created_by)
                """
            ),
            {
                "id": org_id,
                "name": "Other Org",
                "slug": org_slug,
                "created_by": created_by_user_id,
            },
        )
    return org_id
