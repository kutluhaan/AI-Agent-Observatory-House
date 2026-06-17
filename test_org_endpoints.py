"""
Integration Testleri — Organization + Davet Sistemi (M5)

Spec'ten kapsam:
- Org oluşturma — slug unique, owner otomatik eklenir
- Üye yönetimi — rol değiştirme, çıkarma
- Davet akışı — gönder → kabul et → üye oldu
- RBAC — member admin endpoint'ine erişemez
- Edge case'ler: email mismatch, expired token, already member
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.auth import OrganizationInvitation
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.services import jwt_service
from app.services.password_service import hash_password
from app.services.token_store import store_invite_token


# ─── Org Oluşturma ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_org_success(client, db, test_user):
    """Login → org oluştur → owner olarak üye eklendi."""
    login = await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    assert login.status_code == 200

    resp = await client.post("/organizations", json={
        "name": "My Company",
        "slug": f"my-company-{uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["role"] == "owner"
    assert data["slug"].startswith("my-company")


@pytest.mark.asyncio
async def test_create_org_duplicate_slug(client, db, test_user, test_org):
    """Spec: SLUG_ALREADY_EXISTS → 409."""
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    resp = await client.post("/organizations", json={
        "name": "Another Org",
        "slug": test_org.slug,
    })
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SLUG_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_org_invalid_slug(client, db, test_user):
    """Spec: INVALID_SLUG_FORMAT → 422."""
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    resp = await client.post("/organizations", json={
        "name": "Bad Slug Org",
        "slug": "UPPERCASE-NOT-ALLOWED",
    })
    assert resp.status_code in (422, 422)


@pytest.mark.asyncio
async def test_create_org_requires_auth(client, db):
    """Auth olmadan org oluşturulamaz."""
    resp = await client.post("/organizations", json={
        "name": "Test", "slug": "test-slug"
    })
    assert resp.status_code == 401


# ─── Org Bilgisi ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_org_success(client, db, test_user, test_org):
    """Member org bilgisini görebilir."""
    # test_org token'a yansıması için switch-org yapmalıyız
    # Önce login — test_org'un sahibi test_user
    login = await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    assert login.status_code == 200

    # Switch-org ile org context'ini al
    switch = await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})
    assert switch.status_code == 200

    resp = await client.get(f"/organizations/{test_org.id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["slug"] == test_org.slug
    assert "member_count" in data


@pytest.mark.asyncio
async def test_get_org_wrong_org_id(client, db, test_user, test_org):
    """Spec: Yanlış org'a istek → 403 (token'daki org farklı)."""
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    wrong_id = uuid.uuid4()
    resp = await client.get(f"/organizations/{wrong_id}")
    assert resp.status_code == 403


# ─── Üye Yönetimi ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_members(client, db, test_user, test_org):
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.get(f"/organizations/{test_org.id}/members")
    assert resp.status_code == 200
    members = resp.json()["data"]
    assert len(members) >= 1
    assert any(m["email"] == test_user.email for m in members)


@pytest.mark.asyncio
async def test_member_cannot_list_members_of_other_org(client, db, test_user):
    """Spec: Yanlış org'a istek → 403."""
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    # Farklı bir org_id — token'da bu org yok
    resp = await client.get(f"/organizations/{uuid.uuid4()}/members")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_owner_can_update_member_role(client, db, test_user, test_org):
    """Owner üye rolünü değiştirebilir."""
    # Önce admin olmayan bir üye ekle
    member_user = User(
        email=f"member-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Member User",
        is_verified=True,
        is_active=True,
    )
    db.add(member_user)
    await db.flush()

    membership = OrganizationMember(
        organization_id=test_org.id,
        user_id=member_user.id,
        role="member",
    )
    db.add(membership)
    await db.flush()

    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.patch(
        f"/organizations/{test_org.id}/members/{member_user.id}",
        json={"role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "admin"


@pytest.mark.asyncio
async def test_cannot_change_own_role(client, db, test_user, test_org):
    """Spec: CANNOT_CHANGE_OWN_ROLE → 422."""
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.patch(
        f"/organizations/{test_org.id}/members/{test_user.id}",
        json={"role": "admin"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CANNOT_CHANGE_OWN_ROLE"


@pytest.mark.asyncio
async def test_cannot_remove_owner(client, db, test_user, test_org):
    """Spec: CANNOT_REMOVE_OWNER → 422."""
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.delete(
        f"/organizations/{test_org.id}/members/{test_user.id}"
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CANNOT_REMOVE_OWNER"


# ─── RBAC ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_member_cannot_send_invitation(client, db, test_user, test_org):
    """Spec: member davet gönderemiyor → 403."""
    # Member user oluştur
    member_user = User(
        email=f"member2-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Member User",
        is_verified=True,
        is_active=True,
    )
    db.add(member_user)
    await db.flush()
    db.add(OrganizationMember(
        organization_id=test_org.id,
        user_id=member_user.id,
        role="member",
    ))
    await db.flush()

    # Member olarak login
    await client.post("/auth/login", json={
        "email": member_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.post(
        f"/organizations/{test_org.id}/invitations",
        json={"email": "newuser@test.com", "role": "member"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_member_cannot_delete_org(client, db, test_user, test_org):
    """Spec: member org silemez → 403."""
    member_user = User(
        email=f"member3-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Member",
        is_verified=True,
        is_active=True,
    )
    db.add(member_user)
    await db.flush()
    db.add(OrganizationMember(
        organization_id=test_org.id,
        user_id=member_user.id,
        role="member",
    ))
    await db.flush()

    await client.post("/auth/login", json={
        "email": member_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.delete(f"/organizations/{test_org.id}")
    assert resp.status_code == 403


# ─── Davet Akışı ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_invitation_full_flow(client, db, test_user, test_org, redis):
    """Spec: Owner davet gönderir → kullanıcı kabul eder → org'a katılır."""
    # Davet edilecek kullanıcı
    invited_user = User(
        email=f"invited-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Invited User",
        is_verified=True,
        is_active=True,
    )
    db.add(invited_user)
    await db.flush()

    # Owner login ve davet gönder
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    invite_resp = await client.post(
        f"/organizations/{test_org.id}/invitations",
        json={"email": invited_user.email, "role": "member"},
    )
    assert invite_resp.status_code == 201

    # DB'den raw token'ı al
    inv_result = await db.execute(
        select(OrganizationInvitation).where(
            OrganizationInvitation.email == invited_user.email
        )
    )
    invitation = inv_result.scalar_one_or_none()
    assert invitation is not None
    assert invitation.status == "pending"

    # Raw token'ı bul (hash'ten reverse edilemez, DB'den test için)
    # Test için direkt token üretip Redis'e yaz
    raw_token = jwt_service.generate_secure_token()
    token_hash = jwt_service.hash_token(raw_token)
    invitation.token_hash = token_hash
    await db.flush()
    await store_invite_token(redis, token_hash, str(invitation.id))

    # Invited user login ve daveti kabul et
    await client.post("/auth/logout")
    await client.post("/auth/login", json={
        "email": invited_user.email, "password": "Test1234!"
    })

    accept_resp = await client.post(f"/invitations/{raw_token}/accept")
    assert accept_resp.status_code == 200
    data = accept_resp.json()["data"]
    assert data["role"] == "member"
    assert data["organization"]["slug"] == test_org.slug

    # Üyelik oluştu mu?
    membership = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == test_org.id,
            OrganizationMember.user_id == invited_user.id,
        )
    )
    assert membership.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_invitation_email_mismatch(client, db, test_user, test_org, redis):
    """Spec: EMAIL_MISMATCH — farklı email ile login edip kabul etmeye çalışma."""
    # Farklı kullanıcı
    other_user = User(
        email=f"other-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Other User",
        is_verified=True,
        is_active=True,
    )
    db.add(other_user)
    await db.flush()

    # Davet oluştur (farklı email'e)
    invited_email = f"invited-{uuid.uuid4().hex[:6]}@example.com"
    raw_token = jwt_service.generate_secure_token()
    token_hash = jwt_service.hash_token(raw_token)

    invitation = OrganizationInvitation(
        organization_id=test_org.id,
        invited_by=test_user.id,
        email=invited_email,
        role="member",
        token_hash=token_hash,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()
    await store_invite_token(redis, token_hash, str(invitation.id))

    # Farklı kullanıcı ile login et
    await client.post("/auth/login", json={
        "email": other_user.email, "password": "Test1234!"
    })

    resp = await client.post(f"/invitations/{raw_token}/accept")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "EMAIL_MISMATCH"


@pytest.mark.asyncio
async def test_invitation_already_pending(client, db, test_user, test_org):
    """Spec: INVITATION_ALREADY_PENDING — aynı email'e iki davet."""
    invited_email = f"dup-{uuid.uuid4().hex[:6]}@example.com"

    # Mevcut pending davet ekle
    invitation = OrganizationInvitation(
        organization_id=test_org.id,
        invited_by=test_user.id,
        email=invited_email,
        role="member",
        token_hash=jwt_service.hash_token(jwt_service.generate_secure_token()),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()

    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.post(
        f"/organizations/{test_org.id}/invitations",
        json={"email": invited_email, "role": "member"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVITATION_ALREADY_PENDING"


@pytest.mark.asyncio
async def test_cancel_invitation(client, db, test_user, test_org, redis):
    """Owner daveti iptal edebilir."""
    raw_token = jwt_service.generate_secure_token()
    token_hash = jwt_service.hash_token(raw_token)

    invitation = OrganizationInvitation(
        organization_id=test_org.id,
        invited_by=test_user.id,
        email=f"cancel-{uuid.uuid4().hex[:6]}@example.com",
        role="member",
        token_hash=token_hash,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    await db.flush()
    await store_invite_token(redis, token_hash, str(invitation.id))

    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })
    await client.post("/auth/switch-org", json={"org_id": str(test_org.id)})

    resp = await client.delete(
        f"/organizations/{test_org.id}/invitations/{invitation.id}"
    )
    assert resp.status_code == 204

    # Status cancelled oldu mu?
    await db.refresh(invitation)
    assert invitation.status == "cancelled"


@pytest.mark.asyncio
async def test_accept_already_used_invitation(client, db, test_user, test_org, redis):
    """Spec: INVITATION_ALREADY_USED — zaten kabul edilmiş davet."""
    invited_user = User(
        email=f"used-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("Test1234!"),
        full_name="Used",
        is_verified=True,
        is_active=True,
    )
    db.add(invited_user)
    await db.flush()

    raw_token = jwt_service.generate_secure_token()
    token_hash = jwt_service.hash_token(raw_token)

    invitation = OrganizationInvitation(
        organization_id=test_org.id,
        invited_by=test_user.id,
        email=invited_user.email,
        role="member",
        token_hash=token_hash,
        status="accepted",  # Zaten kabul edilmiş
        expires_at=datetime.now(UTC) + timedelta(days=7),
        accepted_at=datetime.now(UTC),
    )
    db.add(invitation)
    await db.flush()
    await store_invite_token(redis, token_hash, str(invitation.id))

    await client.post("/auth/login", json={
        "email": invited_user.email, "password": "Test1234!"
    })

    resp = await client.post(f"/invitations/{raw_token}/accept")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVITATION_ALREADY_USED"


@pytest.mark.asyncio
async def test_org_delete_hard_delete(client, db, test_user):
    """Spec: Org silme hard delete — tüm veriler gider."""
    # Yeni org oluştur
    await client.post("/auth/login", json={
        "email": test_user.email, "password": "Test1234!"
    })

    slug = f"delete-me-{uuid.uuid4().hex[:6]}"
    create_resp = await client.post("/organizations", json={
        "name": "Delete Me", "slug": slug
    })
    assert create_resp.status_code == 201
    org_id = create_resp.json()["data"]["id"]

    # Org'a geç
    await client.post("/auth/switch-org", json={"org_id": org_id})

    # Sil
    resp = await client.delete(f"/organizations/{org_id}")
    assert resp.status_code == 204

    # DB'de yok mu?
    org = await db.get(Organization, uuid.UUID(org_id))
    assert org is None
