"""
Unit Testler — Provider Factory + Base Tipler

DB mock kullanılır. Gerçek provider çağrısı yapılmaz.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.responses import AppError
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.base import (
    CompletionResult,
    Message,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderRequestError,
    StreamEvent,
    ToolDefinition,
)
from app.services.providers.factory import SUPPORTED_PROVIDERS, get_provider
from app.services.providers.gemini_provider import GeminiProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_provider import OpenAIProvider


# ─── Base Types ───────────────────────────────────────────

def test_stream_event_to_dict_token():
    event = StreamEvent(type="token", content="hello")
    d = event.to_dict()
    assert d == {"type": "token", "content": "hello"}


def test_stream_event_to_dict_done():
    event = StreamEvent(type="done", finish_reason="stop")
    d = event.to_dict()
    assert d == {"type": "done", "finish_reason": "stop"}


def test_stream_event_to_dict_error():
    event = StreamEvent(type="error", error_message="boom")
    d = event.to_dict()
    assert d == {"type": "error", "message": "boom"}


def test_stream_event_to_dict_tool_call():
    event = StreamEvent(type="tool_call", tool_call={"name": "search", "arguments": "{}"})
    d = event.to_dict()
    assert d["tool_call"]["name"] == "search"


def test_message_default_fields():
    m = Message(role="user", content="hi")
    assert m.tool_call_id is None
    assert m.tool_calls is None


def test_completion_result_defaults():
    r = CompletionResult(content="hi", finish_reason="stop")
    assert r.tool_calls == []
    assert r.usage == {}


def test_provider_auth_error_status_code():
    err = ProviderAuthError("bad key")
    assert err.code == "PROVIDER_AUTH_FAILED"
    assert err.status_code == 401


def test_provider_rate_limit_error_status_code():
    err = ProviderRateLimitError()
    assert err.code == "PROVIDER_RATE_LIMITED"
    assert err.status_code == 429


def test_provider_request_error_status_code():
    err = ProviderRequestError()
    assert err.code == "PROVIDER_REQUEST_FAILED"
    assert err.status_code == 502


# ─── Provider Instantiation ───────────────────────────────

def test_openai_provider_name():
    p = OpenAIProvider(api_key="sk-test")
    assert p.name == "openai"
    assert p.supports_tools is True


def test_anthropic_provider_name():
    p = AnthropicProvider(api_key="sk-ant-test")
    assert p.name == "anthropic"
    assert p.supports_tools is True


def test_gemini_provider_name():
    p = GeminiProvider(api_key="gm-test")
    assert p.name == "gemini"
    assert p.supports_tools is True


def test_ollama_provider_name():
    p = OllamaProvider(base_url="http://localhost:11434")
    assert p.name == "ollama"


def test_ollama_provider_strips_trailing_slash():
    p = OllamaProvider(base_url="http://localhost:11434/")
    assert p._base_url == "http://localhost:11434"


# ─── Factory ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_factory_rejects_unsupported_provider():
    db = AsyncMock()
    with pytest.raises(AppError) as exc:
        await get_provider(db, uuid.uuid4(), "made-up-provider")
    assert exc.value.code == "PROVIDER_NOT_SUPPORTED"
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_factory_falls_back_to_platform_openai_key(monkeypatch):
    """Org credential yoksa .env'deki key kullanılmalı."""
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "sk-platform-key")

    # DB'de credential yok
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    provider = await get_provider(db, uuid.uuid4(), "openai")
    assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_factory_raises_when_no_key_anywhere(monkeypatch):
    """Org'da yok, platform'da yok → PROVIDER_NOT_CONFIGURED."""
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "")

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(AppError) as exc:
        await get_provider(db, uuid.uuid4(), "openai")
    assert exc.value.code == "PROVIDER_NOT_CONFIGURED"
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_factory_custom_uses_env_base_url(monkeypatch):
    """Custom: org credential yoksa .env CUSTOM_BASE_URL kullanılmalı (F3)."""
    monkeypatch.setattr("app.services.providers.factory.settings.custom_base_url", "http://gpu:8000/v1")
    monkeypatch.setattr("app.services.providers.factory.settings.custom_api_key", "")

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    provider = await get_provider(db, uuid.uuid4(), "custom")
    assert isinstance(provider, OpenAIProvider)
    assert str(provider._client.base_url).startswith("http://gpu:8000/v1")


@pytest.mark.asyncio
async def test_factory_custom_no_base_url_raises(monkeypatch):
    """Custom: ne org ne env'de base_url → PROVIDER_NOT_CONFIGURED."""
    monkeypatch.setattr("app.services.providers.factory.settings.custom_base_url", "")

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(AppError) as exc:
        await get_provider(db, uuid.uuid4(), "custom")
    assert exc.value.code == "PROVIDER_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_factory_uses_org_credential_over_platform(monkeypatch):
    """Org'un kendi key'i varsa platform key'ine düşülmemeli."""
    monkeypatch.setattr("app.services.providers.factory.settings.openai_api_key", "sk-platform-key")

    from app.core.encryption import encrypt_value

    mock_credential = MagicMock()
    mock_credential.encrypted_key = encrypt_value("sk-org-specific-key")
    mock_credential.base_url = None

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_credential
    db.execute = AsyncMock(return_value=result_mock)

    provider = await get_provider(db, uuid.uuid4(), "openai")
    assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_factory_ollama_falls_back_to_platform_base_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.providers.factory.settings.ollama_base_url", "http://platform-ollama:11434"
    )

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    provider = await get_provider(db, uuid.uuid4(), "ollama")
    assert isinstance(provider, OllamaProvider)
    assert provider._base_url == "http://platform-ollama:11434"


@pytest.mark.asyncio
async def test_factory_ollama_raises_when_no_base_url(monkeypatch):
    monkeypatch.setattr("app.services.providers.factory.settings.ollama_base_url", "")

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(AppError) as exc:
        await get_provider(db, uuid.uuid4(), "ollama")
    assert exc.value.code == "PROVIDER_NOT_CONFIGURED"


def test_supported_providers_set():
    assert SUPPORTED_PROVIDERS == {"openai", "anthropic", "gemini", "ollama", "custom", "http"}


@pytest.mark.asyncio
async def test_get_provider_for_agent_http_uses_endpoint():
    """F7.1: provider='http' → agent endpoint'iyle OpenAIProvider."""
    from types import SimpleNamespace
    from app.services.providers.factory import get_provider_for_agent

    agent = SimpleNamespace(
        provider="http", endpoint_url="http://ext-agent:9000/v1",
        endpoint_api_key=None, organization_id=uuid.uuid4(),
    )
    provider = await get_provider_for_agent(AsyncMock(), agent)
    assert isinstance(provider, OpenAIProvider)
    assert str(provider._client.base_url).startswith("http://ext-agent:9000/v1")


@pytest.mark.asyncio
async def test_get_provider_for_agent_http_requires_url():
    from types import SimpleNamespace
    from app.services.providers.factory import get_provider_for_agent

    agent = SimpleNamespace(
        provider="http", endpoint_url=None, endpoint_api_key=None,
        organization_id=uuid.uuid4(),
    )
    with pytest.raises(AppError) as exc:
        await get_provider_for_agent(AsyncMock(), agent)
    assert exc.value.code == "PROVIDER_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_get_provider_for_agent_http_requires_url_via_factory():
    """get_provider doğrudan 'http' ile çağrılırsa per-agent uyarısı verir."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)
    with pytest.raises(AppError) as exc:
        await get_provider(db, uuid.uuid4(), "http")
    assert exc.value.code == "PROVIDER_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_factory_falls_back_to_platform_gemini_key(monkeypatch):
    """Org credential yoksa .env'deki gemini key kullanılmalı."""
    monkeypatch.setattr("app.services.providers.factory.settings.gemini_api_key", "gm-platform-key")

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    provider = await get_provider(db, uuid.uuid4(), "gemini")
    assert isinstance(provider, GeminiProvider)
