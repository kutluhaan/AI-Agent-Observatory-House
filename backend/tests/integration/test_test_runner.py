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
async def other_client():
    """Bağımsız client (ayrı cookie jar) — owner_client ile aynı `client` fixture'ını
    paylaşmamalı, yoksa ikisi tek org'a çözülür ve izolasyon testi anlamsızlaşır."""
    from httpx import ASGITransport
    from app.core.redis import get_redis_pool
    from app.main import app

    await get_redis_pool()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"ts-other-{uuid.uuid4().hex[:8]}@example.com"
        user_id = await register_and_verify(ac, email=email, password="Test1234!", full_name="Other")
        org_id, _ = seed_organization(user_id)
        await login_user(ac, email=email, password="Test1234!")
        await ac.post("/auth/switch-org", json={"org_id": org_id})
        yield ac, org_id, user_id


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


# ─── F4.2: Suite KPI seçimi ───────────────────────────────

@pytest.mark.asyncio
async def test_kpi_catalog_endpoint(owner_client):
    client, _, _ = owner_client
    resp = await client.get("/test-suites/kpi-catalog")
    assert resp.status_code == 200
    data = assert_success(resp.json())
    keys = {c["key"] for c in data["catalog"]}
    assert "success_run_rate" in keys
    assert "avg_judge_score" in keys
    assert set(data["defaults"]).issubset(keys)


@pytest.mark.asyncio
async def test_create_suite_defaults_kpis_null(owner_client):
    client, _, _ = owner_client
    data = assert_success((await _create_suite(client)).json())
    assert data["kpis"] is None  # NULL → frontend varsayılanı kullanır


@pytest.mark.asyncio
async def test_update_suite_kpis_persists(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]

    chosen = ["success_run_rate", "avg_judge_score"]
    resp = await client.patch(f"/test-suites/{suite_id}", json={"kpis": chosen})
    assert resp.status_code == 200
    assert assert_success(resp.json())["kpis"] == chosen

    # Kalıcı: tekrar GET'te aynen gelmeli
    again = assert_success((await client.get(f"/test-suites/{suite_id}")).json())
    assert again["kpis"] == chosen


@pytest.mark.asyncio
async def test_update_suite_kpis_null_resets(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    await client.patch(f"/test-suites/{suite_id}", json={"kpis": ["avg_cost_usd"]})
    resp = await client.patch(f"/test-suites/{suite_id}", json={"kpis": None})
    assert assert_success(resp.json())["kpis"] is None


@pytest.mark.asyncio
async def test_update_suite_invalid_kpi_returns_422(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    resp = await client.patch(f"/test-suites/{suite_id}", json={"kpis": ["made_up_kpi"]})
    assert resp.status_code == 422


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


# ─── F4.3: A/B Prompt Experiments ─────────────────────────

_VARIANTS = [
    {"label": "Kısa", "system_prompt": "Be brief."},
    {"label": "Detaylı", "system_prompt": "Be very detailed."},
]


def _patch_runner():
    return patch(
        "app.services.test_suite.experiment_runner.ExperimentRunner.run",
        new_callable=AsyncMock,
    )


@pytest.mark.asyncio
async def test_run_experiment_creates_variant_runs(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    with _patch_runner():
        resp = await client.post(f"/test-suites/{suite_id}/experiments", json={"variants": _VARIANTS})
    assert resp.status_code == 202
    data = assert_success(resp.json())
    assert "experiment_id" in data
    assert len(data["variants"]) == 2
    assert {v["variant_label"] for v in data["variants"]} == {"Kısa", "Detaylı"}
    assert all(v["status"] == "pending" for v in data["variants"])
    assert any(v["system_prompt_override"] == "Be brief." for v in data["variants"])


@pytest.mark.asyncio
async def test_run_experiment_requires_two_variants(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    resp = await client.post(f"/test-suites/{suite_id}/experiments", json={"variants": [_VARIANTS[0]]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_experiment_duplicate_labels_422(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    dup = [{"label": "X", "system_prompt": "a"}, {"label": "X", "system_prompt": "b"}]
    resp = await client.post(f"/test-suites/{suite_id}/experiments", json={"variants": dup})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_and_get_experiment(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    with _patch_runner():
        exp = assert_success(
            (await client.post(f"/test-suites/{suite_id}/experiments", json={"variants": _VARIANTS})).json()
        )
    exp_id = exp["experiment_id"]

    listed = assert_success((await client.get(f"/test-suites/{suite_id}/experiments")).json())
    assert any(e["experiment_id"] == exp_id for e in listed)

    detail = assert_success((await client.get(f"/test-suites/{suite_id}/experiments/{exp_id}")).json())
    assert detail["experiment_id"] == exp_id
    assert len(detail["variants"]) == 2
    # varyant run'ları normal runs listesinde de görünür + variant_label taşır
    runs = assert_success((await client.get(f"/test-suites/{suite_id}/runs")).json())
    assert any(r.get("variant_label") == "Kısa" for r in runs)


@pytest.mark.asyncio
async def test_get_experiment_not_found(owner_client):
    client, _, _ = owner_client
    suite_id = assert_success((await _create_suite(client)).json())["id"]
    resp = await client.get(f"/test-suites/{suite_id}/experiments/{uuid.uuid4()}")
    assert resp.status_code == 404


# ─── F6: Senaryo (çok-adımlı) suite oluşturma ─────────────

_SCENARIO_YAML = """
name: scenario-suite
cases:
  - name: multi-turn
    steps:
      - input: "Paris uçuşu bul"
        assertions:
          - type: response_contains
            value: "Paris"
      - input: "En ucuzunu seç"
        assertions:
          - type: response_not_contains
            value: "error"
"""


@pytest.mark.asyncio
async def test_create_scenario_suite_succeeds(owner_client):
    client, _, _ = owner_client
    resp = await _create_suite(client, yaml=_SCENARIO_YAML)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_scenario_invalid_step_returns_422(owner_client):
    client, _, _ = owner_client
    bad = "name: s\ncases:\n  - name: c\n    steps:\n      - assertions: []\n"  # input yok
    resp = await _create_suite(client, yaml=bad)
    assert resp.status_code == 422


# ─── B2: dataset'ten suite ────────────────────────────────

async def _make_agent(client) -> str:
    r = await client.post("/agents", json={
        "name": f"ds-agent-{uuid.uuid4().hex[:6]}", "system_prompt": "x",
        "provider": "openai", "model": "gpt-4o-mini",
    })
    return assert_success(r.json())["id"]


@pytest.mark.asyncio
async def test_create_suite_from_csv_dataset(owner_client):
    client, _, _ = owner_client
    aid = await _make_agent(client)
    resp = await client.post("/test-suites/from-dataset", json={
        "name": f"ds-{uuid.uuid4().hex[:6]}", "agent_id": aid,
        "format": "csv", "content": "input,expected\nMerhaba,selam\n2+2,4\n", "assertion": "contains",
    })
    assert resp.status_code == 201
    data = assert_success(resp.json())
    assert data["cases_created"] == 2


@pytest.mark.asyncio
async def test_create_suite_from_jsonl_dataset(owner_client):
    client, _, _ = owner_client
    aid = await _make_agent(client)
    resp = await client.post("/test-suites/from-dataset", json={
        "name": f"ds-{uuid.uuid4().hex[:6]}", "agent_id": aid,
        "format": "jsonl", "content": '{"input":"a","expected":"b"}\n{"input":"c"}\n',
    })
    assert resp.status_code == 201
    assert assert_success(resp.json())["cases_created"] == 2


@pytest.mark.asyncio
async def test_from_dataset_invalid_returns_422(owner_client):
    client, _, _ = owner_client
    aid = await _make_agent(client)
    resp = await client.post("/test-suites/from-dataset", json={
        "name": f"ds-{uuid.uuid4().hex[:6]}", "agent_id": aid,
        "format": "csv", "content": "foo,bar\n1,2\n",  # input sütunu yok
    })
    assert resp.status_code == 422
    assert_error(resp.json(), "INVALID_DATASET")


@pytest.mark.asyncio
async def test_from_dataset_agent_not_found_422(owner_client):
    client, _, _ = owner_client
    resp = await client.post("/test-suites/from-dataset", json={
        "name": f"ds-{uuid.uuid4().hex[:6]}", "agent_id": str(uuid.uuid4()),
        "format": "jsonl", "content": '{"input":"a"}\n',
    })
    assert resp.status_code == 422
    assert_error(resp.json(), "AGENT_NOT_FOUND")


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
