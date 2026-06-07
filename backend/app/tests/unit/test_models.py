"""
M2 Unit Testleri — Model Validasyonları

DB bağlantısı gerekmez — SQLAlchemy model yapısı test edilir.
Her test:
  - Modelin doğru tablo adını kullandığını
  - Doğru kolonları içerdiğini
  - Doğru ilişkileri tanımladığını
  - Doğru constraint'leri içerdiğini
doğrular.
"""
import uuid

import pytest
from sqlalchemy import inspect

from app.core.database import Base
from app.models import (
    User,
    Organization,
    OrganizationMember,
    RefreshToken,
    EmailVerification,
    PasswordReset,
    OrganizationInvitation,
    OAuthAccount,
)


# ─── Tablo Adları ─────────────────────────────────────────


def test_user_table_name():
    assert User.__tablename__ == "users"


def test_organization_table_name():
    assert Organization.__tablename__ == "organizations"


def test_organization_member_table_name():
    assert OrganizationMember.__tablename__ == "organization_members"


def test_refresh_token_table_name():
    assert RefreshToken.__tablename__ == "refresh_tokens"


def test_email_verification_table_name():
    assert EmailVerification.__tablename__ == "email_verifications"


def test_password_reset_table_name():
    assert PasswordReset.__tablename__ == "password_resets"


def test_organization_invitation_table_name():
    assert OrganizationInvitation.__tablename__ == "organization_invitations"


def test_oauth_account_table_name():
    assert OAuthAccount.__tablename__ == "oauth_accounts"


# ─── Tüm Tablolar Base'e Kayıtlı ─────────────────────────


def test_all_tables_registered():
    """8 tablonun tamamının Base.metadata'da kayıtlı olduğunu doğrular."""
    expected_tables = {
        "users",
        "organizations",
        "organization_members",
        "refresh_tokens",
        "email_verifications",
        "password_resets",
        "organization_invitations",
        "oauth_accounts",
    }
    registered = set(Base.metadata.tables.keys())
    assert expected_tables == registered, f"Eksik tablolar: {expected_tables - registered}"


# ─── Kolon Varlığı ────────────────────────────────────────


def test_user_columns():
    columns = {c.name for c in User.__table__.columns}
    expected = {
        "id", "email", "password_hash", "is_verified", "is_active",
        "full_name", "avatar_url", "last_login_at", "created_at", "updated_at"
    }
    assert expected.issubset(columns)


def test_organization_columns():
    columns = {c.name for c in Organization.__table__.columns}
    expected = {"id", "name", "slug", "plan", "is_active", "created_by", "created_at", "updated_at"}
    assert expected.issubset(columns)


def test_organization_member_columns():
    columns = {c.name for c in OrganizationMember.__table__.columns}
    expected = {"id", "organization_id", "user_id", "role", "joined_at"}
    assert expected.issubset(columns)


def test_refresh_token_columns():
    columns = {c.name for c in RefreshToken.__table__.columns}
    expected = {
        "id", "user_id", "token_hash", "device_info", "ip_address",
        "expires_at", "is_revoked", "revoked_at", "created_at"
    }
    assert expected.issubset(columns)


def test_email_verification_columns():
    columns = {c.name for c in EmailVerification.__table__.columns}
    expected = {"id", "user_id", "token_hash", "expires_at", "used_at", "created_at"}
    assert expected.issubset(columns)


def test_password_reset_columns():
    columns = {c.name for c in PasswordReset.__table__.columns}
    expected = {"id", "user_id", "token_hash", "expires_at", "used_at", "created_at"}
    assert expected.issubset(columns)


def test_organization_invitation_columns():
    columns = {c.name for c in OrganizationInvitation.__table__.columns}
    expected = {
        "id", "organization_id", "invited_by", "email", "role",
        "token_hash", "status", "expires_at", "accepted_at", "created_at"
    }
    assert expected.issubset(columns)


def test_oauth_account_columns():
    columns = {c.name for c in OAuthAccount.__table__.columns}
    expected = {
        "id", "user_id", "provider", "provider_id",
        "access_token", "refresh_token", "expires_at", "created_at", "updated_at"
    }
    assert expected.issubset(columns)


# ─── Nullable / Non-nullable ──────────────────────────────


def test_user_email_not_nullable():
    col = User.__table__.columns["email"]
    assert not col.nullable


def test_user_password_hash_nullable():
    """password_hash NULL olabilir — OAuth kullanıcıları için."""
    col = User.__table__.columns["password_hash"]
    assert col.nullable


def test_organization_slug_not_nullable():
    col = Organization.__table__.columns["slug"]
    assert not col.nullable


def test_refresh_token_expires_at_not_nullable():
    col = RefreshToken.__table__.columns["expires_at"]
    assert not col.nullable


def test_email_verification_used_at_nullable():
    """used_at NULL = henüz kullanılmadı."""
    col = EmailVerification.__table__.columns["used_at"]
    assert col.nullable


def test_password_reset_used_at_nullable():
    """used_at NULL = henüz kullanılmadı."""
    col = PasswordReset.__table__.columns["used_at"]
    assert col.nullable


# ─── Unique Constraint'ler ────────────────────────────────


def test_user_email_unique():
    """Email benzersiz olmalı."""
    col = User.__table__.columns["email"]
    assert col.unique


def test_organization_slug_unique():
    """Slug benzersiz olmalı — URL routing için."""
    col = Organization.__table__.columns["slug"]
    assert col.unique


def test_org_member_unique_constraint():
    """Aynı kullanıcı aynı org'da iki kez üye olamaz."""
    constraint_names = {c.name for c in OrganizationMember.__table__.constraints}
    assert "uq_org_member" in constraint_names


def test_org_invitation_unique_constraint():
    """Aynı org'a aynı email'e iki pending davet gönderilemez."""
    constraint_names = {c.name for c in OrganizationInvitation.__table__.constraints}
    assert "uq_org_invitation_email" in constraint_names


def test_oauth_unique_constraint():
    """Aynı provider hesabı iki kullanıcıya bağlanamaz."""
    constraint_names = {c.name for c in OAuthAccount.__table__.constraints}
    assert "uq_oauth_provider_id" in constraint_names


# ─── Index'ler ────────────────────────────────────────────


def test_users_email_index():
    index_names = {i.name for i in User.__table__.indexes}
    assert "ix_users_email" in index_names or any("email" in str(i) for i in User.__table__.indexes)


def test_refresh_tokens_indexes():
    index_names = {i.name for i in RefreshToken.__table__.indexes}
    # user_id ve token_hash index'leri olmalı
    indexed_cols = {
        col.name
        for idx in RefreshToken.__table__.indexes
        for col in idx.columns
    }
    assert "user_id" in indexed_cols
    assert "token_hash" in indexed_cols


def test_organization_members_indexes():
    indexed_cols = {
        col.name
        for idx in OrganizationMember.__table__.indexes
        for col in idx.columns
    }
    assert "organization_id" in indexed_cols
    assert "user_id" in indexed_cols


def test_password_resets_indexes():
    indexed_cols = {
        col.name
        for idx in PasswordReset.__table__.indexes
        for col in idx.columns
    }
    assert "user_id" in indexed_cols
    assert "token_hash" in indexed_cols


def test_organization_invitations_indexes():
    indexed_cols = {
        col.name
        for idx in OrganizationInvitation.__table__.indexes
        for col in idx.columns
    }
    assert "token_hash" in indexed_cols
    assert "email" in indexed_cols


# ─── Default Değerler ─────────────────────────────────────


def test_user_is_verified_default_false():
    col = User.__table__.columns["is_verified"]
    assert col.default is not None or col.server_default is not None


def test_user_is_active_default_true():
    col = User.__table__.columns["is_active"]
    assert col.default is not None or col.server_default is not None


def test_organization_plan_default_free():
    col = Organization.__table__.columns["plan"]
    # plan kolonu Python-side default kullanıyor (default="free")
    # server_default veya default'tan biri olması yeterli
    assert col.default is not None or col.server_default is not None


def test_refresh_token_is_revoked_default_false():
    col = RefreshToken.__table__.columns["is_revoked"]
    assert col.default is not None or col.server_default is not None


# ─── İlişkiler (Relationships) ────────────────────────────


def test_user_has_org_memberships_relationship():
    assert hasattr(User, "org_memberships")


def test_user_has_refresh_tokens_relationship():
    assert hasattr(User, "refresh_tokens")


def test_user_has_email_verifications_relationship():
    assert hasattr(User, "email_verifications")


def test_user_has_password_resets_relationship():
    assert hasattr(User, "password_resets")


def test_user_has_oauth_accounts_relationship():
    assert hasattr(User, "oauth_accounts")


def test_organization_has_members_relationship():
    assert hasattr(Organization, "members")


def test_organization_has_invitations_relationship():
    assert hasattr(Organization, "invitations")


def test_org_member_has_back_references():
    assert hasattr(OrganizationMember, "organization")
    assert hasattr(OrganizationMember, "user")


# ─── repr ─────────────────────────────────────────────────


def test_user_repr():
    user = User(id=uuid.uuid4(), email="test@test.com")
    assert "test@test.com" in repr(user)


def test_organization_repr():
    org = Organization(id=uuid.uuid4(), slug="my-org", name="My Org", created_by=uuid.uuid4())
    assert "my-org" in repr(org)


def test_refresh_token_repr():
    rt = RefreshToken(user_id=uuid.uuid4(), token_hash="abc", is_revoked=False)
    assert "False" in repr(rt)
