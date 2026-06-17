"""
M8 integration — trace pipeline uçtan uca.

test-completion (provider mock) → Redis Stream → (uvicorn container'ının arka plan
consumer'ı) → ClickHouse → GET /traces. Test in-process ASGITransport ile çalışır;
kalıcılaştırmayı çalışan backend container'ının consumer'ı yapar, bu yüzden test
GET /traces'i poll eder (manuel drain yok → yarış/duplikasyon yok).

Gerçek PostgreSQL + Redis + ClickHouse + çalışan backend container gerekir:

    docker compose -f docker-compose.dev.yml exec backend \\
        pytest tests/integration/test_trace_flow.py -v -m integration
"""
from __future__ import annotations

import asyncio
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core import clickhouse
from app.core.redis import get_redis_pool
from app.services.providers.base import CompletionResult
from tests.integration.auth_helpers import (
    assert_error,
    assert_success,
    login_user,
    register_and_verify,
    seed_organization,
)

_COMPLETE = "app.services.providers.openai_provider.OpenAIProvider.complete"


def _require_db() -> None:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — run inside docker backend container")


@pytest.fixture(autouse=True)
async def _schema_ready():
    """ClickHouse şeması var olsun (idempotent) + rate-limit sayaçlarını sıfırla."""
    if not os.environ.get("DATABASE_URL"):
        yield
        return
    await clickhouse.init_schema()
    redis = await get_redis_pool()
    keys = await redis.keys("ratelimit:*")
    if keys:
        await redis.delete(*keys)
    yield


async def _poll_trace(client: AsyncClient, trace_id: str, timeout: float = 6.0) -> dict:
    """Arka plan consumer trace'i ClickHouse'a yazana kadar GET /traces/{id} poll eder."""
    deadline = timeout
    step = 0.25
    waited = 0.0
    while waited < deadline:
        resp = await client.get(f"/traces/{trace_id}")
        if resp.status_code == 200:
            return assert_success(resp.json())
        await asyncio.sleep(step)
        waited += step
    raise AssertionError(f"Trace {trace_id} did not persist within {timeout}s")


async def _owner_org_with_openai(client: AsyncClient, prefix: str = "trace") -> str:
    """Owner + org + yapılandırılmış openai credential. org_id döner, token o org'a switch'li."""
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    password = "Test1234!"
    user_id = await register_and_verify(client, email=email, password=password, full_name="M8 User")
    org_id = seed_organization(user_id, slug=f"{prefix}-{uuid.uuid4().hex[:8]}")[0]
    await login_user(client, email=email, password=password)
    await client.post("/auth/switch-org", json={"org_id": org_id})
    await client.post("/providers", json={"provider": "openai", "api_key": "sk-test-key"})
    return org_id


_FAKE_RESULT = CompletionResult(
    content="Hello from mock!",
    finish_reason="stop",
    usage={"prompt_tokens": 5, "completion_tokens": 3},
)


@pytest.mark.integration
async def test_test_completion_creates_trace(client):
    _require_db()
    await _owner_org_with_openai(client)

    with patch(_COMPLETE, new=AsyncMock(return_value=_FAKE_RESULT)):
        resp = await client.post(
            "/providers/openai/test-completion",
            json={"model": "gpt-4o", "prompt": "hi"},
        )
    assert resp.status_code == 200, resp.text
    data = assert_success(resp.json())
    trace_id = data["trace_id"]
    assert data["content"] == "Hello from mock!"

    # Arka plan consumer persist edene kadar bekle, sonra timeline'ı doğrula
    detail = await _poll_trace(client, trace_id)
    assert detail["name"] == "test-completion:openai"
    assert detail["status"] == "completed"
    types = [e["type"] for e in detail["events"]]
    for expected in ("agent_start", "llm_call_start", "llm_call_end", "agent_end"):
        assert expected in types, f"missing event {expected} in {types}"

    # Liste endpoint'i de trace'i içermeli
    list_resp = await client.get("/traces")
    assert list_resp.status_code == 200
    traces = assert_success(list_resp.json())
    assert any(t["trace_id"] == trace_id for t in traces)


@pytest.mark.integration
async def test_trace_isolation_other_org_cannot_read(client):
    _require_db()
    await _owner_org_with_openai(client, prefix="orga")

    with patch(_COMPLETE, new=AsyncMock(return_value=_FAKE_RESULT)):
        resp = await client.post(
            "/providers/openai/test-completion", json={"model": "gpt-4o", "prompt": "secret"}
        )
    trace_id = assert_success(resp.json())["trace_id"]
    await _poll_trace(client, trace_id)  # org A görebiliyor

    # Farklı org — aynı client'ta yeni owner/org'a geç
    await client.post("/auth/logout")
    await _owner_org_with_openai(client, prefix="orgb")

    detail = await client.get(f"/traces/{trace_id}")
    assert detail.status_code == 404
    assert_error(detail.json(), "TRACE_NOT_FOUND")


@pytest.mark.integration
async def test_get_unknown_trace_404(client):
    _require_db()
    await _owner_org_with_openai(client)
    resp = await client.get(f"/traces/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert_error(resp.json(), "TRACE_NOT_FOUND")


@pytest.mark.integration
async def test_test_completion_requires_configured_provider(client, monkeypatch):
    _require_db()
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "")

    email = f"noprov-{uuid.uuid4().hex[:10]}@example.com"
    user_id = await register_and_verify(client, email=email, password="Test1234!", full_name="Test User")
    org_id = seed_organization(user_id, slug=f"noprov-{uuid.uuid4().hex[:8]}")[0]
    await login_user(client, email=email, password="Test1234!")
    await client.post("/auth/switch-org", json={"org_id": org_id})

    resp = await client.post(
        "/providers/openai/test-completion", json={"model": "gpt-4o", "prompt": "hi"}
    )
    assert resp.status_code == 404
    assert_error(resp.json(), "PROVIDER_NOT_CONFIGURED")


@pytest.mark.integration
async def test_list_traces_requires_org_context(client):
    _require_db()
    email = f"noorg-{uuid.uuid4().hex[:10]}@example.com"
    await register_and_verify(client, email=email, password="Test1234!", full_name="Test User")
    await login_user(client, email=email, password="Test1234!")

    resp = await client.get("/traces")
    assert resp.status_code in (401, 403)
