"""
Integration Testler — M11 Test Core

Kapsam:
  - TestSuite CRUD: oluştur, listele, detay, güncelle, sil
  - Geçersiz YAML → 422 INVALID_TEST_YAML
  - İsim çakışması → 409
  - POST /test-suites/{id}/run → 202 + run_id
  - GET /test-runs/{id} → run detayı + case sonuçları
  - Farklı org izolasyonu

NOT: ExperimentRunner ve AgentRunner mock'lanır.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
)

pytestmark = pytest.mark.integration

VALID_YAML = """
name: my-test-suite
description: "Integration test"
cases:
  - name: basic-echo
    input: "Hello"
    assertions:
      - type: response_contains
        value: "hello"
"""

INVALID_YAML = """
cases:
  - name: no-root-name
    input: x
"""


# ─── Fixtures ─────────────────────────────────────────────

@pytest.fixture
async def owner_client(client: AsyncClient):
    email = f"ts-owner-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Owner")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


@pytest.fixture
async def other_client(client: AsyncClient):
    email = f"ts-other-{uuid.uuid4().hex[:8]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Other")
    org_id, _ = seed_organization(user_id)
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})
    return client, org_id, user_id


async def _create_suite(client, name=None, yaml=VALID_YAML):
    payload = {
        "name": name or f"suite-{uuid.uuid4().hex[:6]}",
        "config_yaml": yaml,
    }
    resp = await client.post("/test-suites", json=payload)
    return resp


# ─── Suite CRUD ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_suite_success(owner_client):
    client, _, _ = owner_client
    resp = await _create_suite(client)
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["name"].startswith("suite-")
    assert "config_yaml" in data


@pytest.mark.asyncio
async def test_create_suite_invalid_yaml_returns_422(owner_client):
    client, _, _ = owner_client
    resp = await _create_suite(client, yaml=INVALID_YAML)
    assert resp.status_code == 422
    assert_error(resp.json(), "INVALID_TEST_YAML")


@pytest.mark.asyncio
async def test_create_suite_name_conflict_returns_409(owner_client):
    client, _, _ = owner_client
    name = f"conflict-{uuid.uuid4().hex[:6]}"
    await _create_suite(client, name=name)
    resp = await _create_suite(client, name=name)
    assert resp.status_code == 409
    assert_error(resp.json(), "SUITE_NAME_CONFLICT")


@pytest.mark.asyncio
async def test_list_suites(owner_client):
    client, _, _ = owner_client
    await _create_suite(client)
    await _create_suite(client)
    resp = await client.get("/test-suites")
    data = assert_success(resp.json())
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_suite_by_id(owner_client):
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]

    resp = await client.get(f"/test-suites/{suite_id}")
    data = assert_success(resp.json())
    assert data["id"] == suite_id


@pytest.mark.asyncio
async def test_get_suite_not_found(owner_client):
    client, _, _ = owner_client
    resp = await client.get(f"/test-suites/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert_error(resp.json(), "SUITE_NOT_FOUND")


@pytest.mark.asyncio
async def test_update_suite_name(owner_client):
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]
    new_name = f"updated-{uuid.uuid4().hex[:6]}"

    resp = await client.patch(f"/test-suites/{suite_id}", json={"name": new_name})
    data = assert_success(resp.json())
    assert data["name"] == new_name


@pytest.mark.asyncio
async def test_update_suite_invalid_yaml_returns_422(owner_client):
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]

    resp = await client.patch(f"/test-suites/{suite_id}", json={"config_yaml": INVALID_YAML})
    assert resp.status_code == 422
    assert_error(resp.json(), "INVALID_TEST_YAML")


@pytest.mark.asyncio
async def test_delete_suite(owner_client):
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]

    del_resp = await client.delete(f"/test-suites/{suite_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/test-suites/{suite_id}")
    assert get_resp.status_code == 404


# ─── Org izolasyonu ───────────────────────────────────────

@pytest.mark.asyncio
async def test_other_org_cannot_see_suite(owner_client, other_client):
    owner, _, _ = owner_client
    other, _, _ = other_client

    create_resp = await _create_suite(owner)
    suite_id = assert_success(create_resp.json())["id"]

    resp = await other.get(f"/test-suites/{suite_id}")
    assert resp.status_code == 404


# ─── Run ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_suite_returns_202(owner_client):
    """POST /test-suites/{id}/run → 202, background task çalışır."""
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]

    # ExperimentRunner'ı mock'la — gerçek agent çağrısı yapmasın
    with patch(
        "app.services.test_suite.experiment_runner.ExperimentRunner.run",
        new_callable=AsyncMock,
    ):
        resp = await client.post(f"/test-suites/{suite_id}/run", json={"parallel": False})

    data = assert_success(resp.json())
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_test_run_returns_detail(owner_client):
    """GET /test-runs/{id} mevcut run'ı döner."""
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]

    with patch(
        "app.services.test_suite.experiment_runner.ExperimentRunner.run",
        new_callable=AsyncMock,
    ):
        run_resp = await client.post(f"/test-suites/{suite_id}/run", json={})

    run_id = assert_success(run_resp.json())["id"]

    detail_resp = await client.get(f"/test-runs/{run_id}")
    detail = assert_success(detail_resp.json())
    assert detail["run"]["id"] == run_id
    assert isinstance(detail["case_results"], list)


@pytest.mark.asyncio
async def test_get_test_run_not_found(owner_client):
    client, _, _ = owner_client
    resp = await client.get(f"/test-runs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert_error(resp.json(), "RUN_NOT_FOUND")


@pytest.mark.asyncio
async def test_list_suite_runs(owner_client):
    """GET /test-suites/{id}/runs → run listesi."""
    client, _, _ = owner_client
    create_resp = await _create_suite(client)
    suite_id = assert_success(create_resp.json())["id"]

    with patch(
        "app.services.test_suite.experiment_runner.ExperimentRunner.run",
        new_callable=AsyncMock,
    ):
        await client.post(f"/test-suites/{suite_id}/run", json={})
        await client.post(f"/test-suites/{suite_id}/run", json={})

    list_resp = await client.get(f"/test-suites/{suite_id}/runs")
    runs = assert_success(list_resp.json())
    assert isinstance(runs, list)
    assert len(runs) >= 2


@pytest.mark.asyncio
async def test_other_org_cannot_access_run(owner_client, other_client):
    owner, _, _ = owner_client
    other, _, _ = other_client

    create_resp = await _create_suite(owner)
    suite_id = assert_success(create_resp.json())["id"]

    with patch(
        "app.services.test_suite.experiment_runner.ExperimentRunner.run",
        new_callable=AsyncMock,
    ):
        run_resp = await owner.post(f"/test-suites/{suite_id}/run", json={})

    run_id = assert_success(run_resp.json())["id"]
    resp = await other.get(f"/test-runs/{run_id}")
    assert resp.status_code == 404
