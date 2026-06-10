"""
M4 Unit Testleri — resolve_active_org

DB bağlantısı gerekmez.
"""
import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.auth import resolve_active_org


def _membership(org_id: uuid.UUID, role: str = "owner") -> SimpleNamespace:
    return SimpleNamespace(organization_id=org_id, role=role)


class TestResolveActiveOrg:
    def test_returns_preferred_org_when_member(self):
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()
        memberships = [_membership(org_a), _membership(org_b, "admin")]

        chosen = resolve_active_org(memberships, org_b)

        assert chosen is not None
        assert chosen.organization_id == org_b
        assert chosen.role == "admin"

    def test_falls_back_to_first_org_when_preferred_not_member(self):
        org_a = uuid.uuid4()
        memberships = [_membership(org_a)]

        chosen = resolve_active_org(memberships, uuid.uuid4())

        assert chosen is not None
        assert chosen.organization_id == org_a

    def test_returns_first_org_when_no_preference(self):
        org_a = uuid.uuid4()
        memberships = [_membership(org_a)]

        chosen = resolve_active_org(memberships, None)

        assert chosen is not None
        assert chosen.organization_id == org_a

    def test_returns_none_when_no_orgs(self):
        assert resolve_active_org([], None) is None
        assert resolve_active_org([], uuid.uuid4()) is None
