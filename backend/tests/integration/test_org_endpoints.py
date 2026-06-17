"""
M5 + M6 integration — organization yönetimi, davet sistemi ve RBAC.

Gerçek PostgreSQL + Redis + JWT (.env) gerekir. M3/M4 ile aynı harness.
Docker backend container içinde çalıştır:

    docker compose -f docker-compose.dev.yml exec backend \\
        pytest tests/integration/test_org_endpoints.py -v -m integration
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    add_member,
    assert_error,
    assert_success,
    get_invitation_status,
    login_user,
    register_and_verify,
    seed_organization,
)


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


# ─── Yardımcılar ──────────────────────────────────────────

async def _new_verified_user(client: AsyncClient, prefix: str = "org") -> tuple[str, str, str]:
    """Register+verify edilmiş kullanıcı. (user_id, email, password) döner."""
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    password = "Test1234!"
    user_id = await register_and_verify(
        client, email=email, password=password, full_name="M5 User"
    )
    return user_id, email, password


async def _create_org_and_switch(client: AsyncClient, slug: str | None = None) -> str:
    """Giriş yapmış kullanıcı için org oluşturur ve token'ı o org'a çevirir. org_id döner."""
    slug = slug or f"org-{uuid.uuid4().hex[:8]}"
    resp = await client.post("/organizations", json={"name": "My Company", "slug": slug})
    assert resp.status_code == 201, resp.text
    org_id = assert_success(resp.json())["id"]
    switch = await client.post("/auth/switch-org", json={"org_id": org_id})
    assert switch.status_code == 200, switch.text
    return org_id


async def _send_invitation(
    client: AsyncClient, org_id: str, email: str, role: str = "member"
):
    """Davet gönderir; (response, raw_token) döner. Email gönderimi patch'lenip token yakalanır."""
    captured: dict[str, str] = {}

    async def _capture(*, email, org_name, invited_by, raw_token, role):  # noqa: A002
        captured["token"] = raw_token
        return True

    with patch("app.api.v1.organizations.send_invitation_email", _capture):
        resp = await client.post(
            f"/organizations/{org_id}/invitations",
            json={"email": email, "role": role},
        )
    return resp, captured.get("token")


# ─── Org Oluşturma ────────────────────────────────────────

@pytest.mark.integration
async def test_create_org_success(client):
    _require_db()
    _, email, password = await _new_verified_user(client)
    await login_user(client, email=email, password=password)

    resp = await client.post(
        "/organizations",
        json={"name": "My Company", "slug": f"my-company-{uuid.uuid4().hex[:6]}"},
    )
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["role"] == "owner"
    assert data["slug"].startswith("my-company")


@pytest.mark.integration
async def test_create_org_duplicate_slug(client):
    _require_db()
    user_id, email, password = await _new_verified_user(client)
    _, existing_slug = seed_organization(user_id, slug=f"dup-{uuid.uuid4().hex[:8]}")
    await login_user(client, email=email, password=password)

    resp = await client.post(
        "/organizations", json={"name": "Another Org", "slug": existing_slug}
    )
    assert resp.status_code == 409
    assert_error(resp.json(), "SLUG_ALREADY_EXISTS")


@pytest.mark.integration
async def test_create_org_invalid_slug(client):
    _require_db()
    _, email, password = await _new_verified_user(client)
    await login_user(client, email=email, password=password)

    resp = await client.post(
        "/organizations", json={"name": "Bad Slug Org", "slug": "UPPERCASE-NOT-ALLOWED"}
    )
    assert resp.status_code == 422


@pytest.mark.integration
async def test_create_org_requires_auth(client):
    _require_db()
    resp = await client.post("/organizations", json={"name": "Test", "slug": "test-slug"})
    assert resp.status_code == 401


# ─── Org Bilgisi ──────────────────────────────────────────

@pytest.mark.integration
async def test_get_org_success(client):
    _require_db()
    _, email, password = await _new_verified_user(client)
    await login_user(client, email=email, password=password)
    org_id = await _create_org_and_switch(client)

    resp = await client.get(f"/organizations/{org_id}")
    assert resp.status_code == 200
    data = assert_success(resp.json())
    assert data["id"] == org_id
    assert data["member_count"] >= 1


@pytest.mark.integration
async def test_get_org_wrong_org_id_returns_403(client):
    _require_db()
    _, email, password = await _new_verified_user(client)
    await login_user(client, email=email, password=password)
    await _create_org_and_switch(client)

    resp = await client.get(f"/organizations/{uuid.uuid4()}")
    assert resp.status_code == 403


# ─── Üye Yönetimi ─────────────────────────────────────────

@pytest.mark.integration
async def test_list_members(client):
    _require_db()
    _, email, password = await _new_verified_user(client)
    await login_user(client, email=email, password=password)
    org_id = await _create_org_and_switch(client)

    resp = await client.get(f"/organizations/{org_id}/members")
    assert resp.status_code == 200
    members = assert_success(resp.json())
    assert any(m["email"] == email for m in members)


@pytest.mark.integration
async def test_member_cannot_list_members_without_org_context(client):
    _require_db()
    _, email, password = await _new_verified_user(client)
    await login_user(client, email=email, password=password)
    # Org context'i yok (switch yapılmadı, hiç org da yok) → role None → 403
    resp = await client.get(f"/organizations/{uuid.uuid4()}/members")
    assert resp.status_code in (401, 403)


@pytest.mark.integration
async def test_owner_can_update_member_role(client):
    _require_db()
    owner_id, owner_email, owner_pw = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]

    member_id, _, _ = await _new_verified_user(client, "member")
    add_member(org_id, member_id, "member")

    await login_user(client, email=owner_email, password=owner_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.patch(
        f"/organizations/{org_id}/members/{member_id}", json={"role": "admin"}
    )
    assert resp.status_code == 200
    assert assert_success(resp.json())["role"] == "admin"


@pytest.mark.integration
async def test_cannot_change_own_role(client):
    _require_db()
    owner_id, email, password = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]
    await login_user(client, email=email, password=password)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.patch(
        f"/organizations/{org_id}/members/{owner_id}", json={"role": "admin"}
    )
    assert resp.status_code == 422
    assert_error(resp.json(), "CANNOT_CHANGE_OWN_ROLE")


@pytest.mark.integration
async def test_cannot_remove_owner(client):
    _require_db()
    owner_id, email, password = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]
    await login_user(client, email=email, password=password)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.delete(f"/organizations/{org_id}/members/{owner_id}")
    assert resp.status_code == 422
    assert_error(resp.json(), "CANNOT_REMOVE_OWNER")


# ─── RBAC ─────────────────────────────────────────────────

@pytest.mark.integration
async def test_member_cannot_send_invitation(client):
    _require_db()
    owner_id, _, _ = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]

    member_id, member_email, member_pw = await _new_verified_user(client, "member")
    add_member(org_id, member_id, "member")

    await login_user(client, email=member_email, password=member_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "newuser@test.com", "role": "member"},
    )
    assert resp.status_code == 403
    assert_error(resp.json(), "INSUFFICIENT_PERMISSIONS")


@pytest.mark.integration
async def test_member_cannot_delete_org(client):
    _require_db()
    owner_id, _, _ = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]

    member_id, member_email, member_pw = await _new_verified_user(client, "member")
    add_member(org_id, member_id, "member")

    await login_user(client, email=member_email, password=member_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.delete(f"/organizations/{org_id}")
    assert resp.status_code == 403


# ─── Davet Akışı ──────────────────────────────────────────

@pytest.mark.integration
async def test_invitation_full_flow(client):
    _require_db()
    owner_id, owner_email, owner_pw = await _new_verified_user(client, "owner")
    org_id, org_slug = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")

    _, invited_email, invited_pw = await _new_verified_user(client, "invited")

    await login_user(client, email=owner_email, password=owner_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    invite_resp, raw_token = await _send_invitation(client, org_id, invited_email)
    assert invite_resp.status_code == 201
    assert raw_token

    # Invited user login ve daveti kabul et
    await client.post("/auth/logout")
    await login_user(client, email=invited_email, password=invited_pw)

    accept = await client.post(f"/invitations/{raw_token}/accept")
    assert accept.status_code == 200
    data = assert_success(accept.json())
    assert data["role"] == "member"
    assert data["organization"]["slug"] == org_slug

    assert get_invitation_status(org_id, invited_email) == "accepted"


@pytest.mark.integration
async def test_invitation_email_mismatch(client):
    _require_db()
    owner_id, owner_email, owner_pw = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]

    invited_email = f"invited-{uuid.uuid4().hex[:8]}@example.com"
    _, other_email, other_pw = await _new_verified_user(client, "other")

    await login_user(client, email=owner_email, password=owner_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})
    invite_resp, raw_token = await _send_invitation(client, org_id, invited_email)
    assert invite_resp.status_code == 201

    # Farklı kullanıcı ile kabul etmeye çalış
    await client.post("/auth/logout")
    await login_user(client, email=other_email, password=other_pw)

    resp = await client.post(f"/invitations/{raw_token}/accept")
    assert resp.status_code == 403
    assert_error(resp.json(), "EMAIL_MISMATCH")


@pytest.mark.integration
async def test_invitation_already_pending(client):
    _require_db()
    owner_id, owner_email, owner_pw = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]
    invited_email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    await login_user(client, email=owner_email, password=owner_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    first, _ = await _send_invitation(client, org_id, invited_email)
    assert first.status_code == 201

    second, _ = await _send_invitation(client, org_id, invited_email)
    assert second.status_code == 409
    assert_error(second.json(), "INVITATION_ALREADY_PENDING")


@pytest.mark.integration
async def test_cancel_invitation(client):
    _require_db()
    owner_id, owner_email, owner_pw = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]
    invited_email = f"cancel-{uuid.uuid4().hex[:8]}@example.com"

    await login_user(client, email=owner_email, password=owner_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})

    invite_resp, _ = await _send_invitation(client, org_id, invited_email)
    invitation_id = assert_success(invite_resp.json())["id"]

    resp = await client.delete(f"/organizations/{org_id}/invitations/{invitation_id}")
    assert resp.status_code == 204
    assert get_invitation_status(org_id, invited_email) == "cancelled"


@pytest.mark.integration
async def test_accept_already_used_invitation(client):
    _require_db()
    owner_id, owner_email, owner_pw = await _new_verified_user(client, "owner")
    org_id = seed_organization(owner_id, slug=f"team-{uuid.uuid4().hex[:8]}")[0]
    _, invited_email, invited_pw = await _new_verified_user(client, "invited")

    await login_user(client, email=owner_email, password=owner_pw)
    await client.post("/auth/switch-org", json={"org_id": org_id})
    invite_resp, raw_token = await _send_invitation(client, org_id, invited_email)
    assert invite_resp.status_code == 201

    await client.post("/auth/logout")
    await login_user(client, email=invited_email, password=invited_pw)

    first = await client.post(f"/invitations/{raw_token}/accept")
    assert first.status_code == 200

    # İkinci kez — token Redis'ten silindiği için EXPIRED, DB'de accepted
    second = await client.post(f"/invitations/{raw_token}/accept")
    assert second.status_code in (409, 410)


# ─── Org Silme ────────────────────────────────────────────

@pytest.mark.integration
async def test_org_delete_hard_delete(client):
    _require_db()
    _, email, password = await _new_verified_user(client, "owner")
    await login_user(client, email=email, password=password)
    org_id = await _create_org_and_switch(client, slug=f"delete-me-{uuid.uuid4().hex[:6]}")

    resp = await client.delete(f"/organizations/{org_id}")
    assert resp.status_code == 204

    # Token hâlâ silinmiş org'u gösteriyor → org bulunamaz (404) veya context geçersiz
    follow = await client.get(f"/organizations/{org_id}")
    assert follow.status_code in (403, 404)
