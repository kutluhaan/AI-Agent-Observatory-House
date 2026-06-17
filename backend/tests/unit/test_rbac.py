"""
Unit Testleri — RBAC (M6)

Spec'ten:
- Her rol için her aksiyon doğru mu
- Member admin endpoint'ine 403 alıyor
- Owner her endpoint'e erişebilir
- Forbidden senaryoları
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from app.api.deps import ROLE_HIERARCHY, TenantContext, require_role
from app.core.responses import ForbiddenError, UnauthorizedError


# ─── TenantContext ────────────────────────────────────────

def test_tenant_context_fields():
    ctx = TenantContext(
        user_id=uuid.uuid4(),
        email="test@test.com",
        jti="test-jti",
        org_id=uuid.uuid4(),
        org_slug="my-org",
        role="owner",
    )
    assert ctx.role == "owner"
    assert ctx.org_slug == "my-org"


def test_tenant_context_nullable_org():
    """Spec: org_id None = org'suz kullanıcı (personal mode)."""
    ctx = TenantContext(
        user_id=uuid.uuid4(),
        email="test@test.com",
        jti="jti",
        org_id=None,
        org_slug=None,
        role=None,
    )
    assert ctx.org_id is None
    assert ctx.role is None


# ─── Role Hierarchy ───────────────────────────────────────

def test_role_hierarchy_order():
    """owner > admin > member."""
    assert ROLE_HIERARCHY.index("owner") > ROLE_HIERARCHY.index("admin")
    assert ROLE_HIERARCHY.index("admin") > ROLE_HIERARCHY.index("member")


def test_all_roles_in_hierarchy():
    assert "owner" in ROLE_HIERARCHY
    assert "admin" in ROLE_HIERARCHY
    assert "member" in ROLE_HIERARCHY


# ─── require_role ─────────────────────────────────────────

def _make_ctx(role: str | None, org_id: uuid.UUID | None = None) -> TenantContext:
    return TenantContext(
        user_id=uuid.uuid4(),
        email="test@test.com",
        jti="test-jti",
        org_id=org_id or (uuid.uuid4() if role else None),
        org_slug="test-org" if role else None,
        role=role,
    )


@pytest.mark.asyncio
async def test_owner_passes_owner_requirement():
    dep = require_role("owner")
    ctx = _make_ctx("owner")
    result = await dep(ctx=ctx)
    assert result.role == "owner"


@pytest.mark.asyncio
async def test_owner_passes_admin_requirement():
    dep = require_role("admin")
    ctx = _make_ctx("owner")
    result = await dep(ctx=ctx)
    assert result.role == "owner"


@pytest.mark.asyncio
async def test_owner_passes_member_requirement():
    dep = require_role("member")
    ctx = _make_ctx("owner")
    result = await dep(ctx=ctx)
    assert result.role == "owner"


@pytest.mark.asyncio
async def test_admin_passes_admin_requirement():
    dep = require_role("admin")
    ctx = _make_ctx("admin")
    result = await dep(ctx=ctx)
    assert result.role == "admin"


@pytest.mark.asyncio
async def test_admin_passes_member_requirement():
    dep = require_role("member")
    ctx = _make_ctx("admin")
    result = await dep(ctx=ctx)
    assert result.role == "admin"


@pytest.mark.asyncio
async def test_admin_fails_owner_requirement():
    """Spec: admin owner endpoint'ine erişemez."""
    dep = require_role("owner")
    ctx = _make_ctx("admin")
    with pytest.raises(ForbiddenError) as exc:
        await dep(ctx=ctx)
    assert exc.value.code == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_member_passes_member_requirement():
    dep = require_role("member")
    ctx = _make_ctx("member")
    result = await dep(ctx=ctx)
    assert result.role == "member"


@pytest.mark.asyncio
async def test_member_fails_admin_requirement():
    """Spec: member admin endpoint'ine 403 alır."""
    dep = require_role("admin")
    ctx = _make_ctx("member")
    with pytest.raises(ForbiddenError) as exc:
        await dep(ctx=ctx)
    assert exc.value.code == "INSUFFICIENT_PERMISSIONS"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_member_fails_owner_requirement():
    dep = require_role("owner")
    ctx = _make_ctx("member")
    with pytest.raises(ForbiddenError) as exc:
        await dep(ctx=ctx)
    assert exc.value.code == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_no_role_fails_any_requirement():
    """Spec: org'suz kullanıcı (role=None) org-scoped endpoint'e erişemez."""
    dep = require_role("member")
    ctx = _make_ctx(None)
    with pytest.raises(ForbiddenError) as exc:
        await dep(ctx=ctx)
    assert exc.value.code == "INSUFFICIENT_PERMISSIONS"


# ─── Permission Matrix (Spec'ten birebir) ────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("role,min_role,should_pass", [
    # Owner — her şeye erişebilir
    ("owner", "owner", True),
    ("owner", "admin", True),
    ("owner", "member", True),
    # Admin
    ("admin", "owner", False),
    ("admin", "admin", True),
    ("admin", "member", True),
    # Member
    ("member", "owner", False),
    ("member", "admin", False),
    ("member", "member", True),
])
async def test_permission_matrix(role, min_role, should_pass):
    dep = require_role(min_role)
    ctx = _make_ctx(role)
    if should_pass:
        result = await dep(ctx=ctx)
        assert result is not None
    else:
        with pytest.raises(ForbiddenError):
            await dep(ctx=ctx)
