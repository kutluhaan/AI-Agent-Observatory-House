"""B1 (#1) — custom HTTP tool: çalıştırıcı + runner routing + şema doğrulama."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.agent.custom_tools as ct
from app.services.agent.base import AgentConfig
from app.services.agent.runner import AgentRunner
from app.schemas.custom_tools import CreateCustomToolRequest


# ─── call_custom_tool (placeholder + GET query / POST body) ───

class _FakeResp:
    def __init__(self, status=200, text="OK"):
        self.status_code = status
        self.text = text


class _FakeClient:
    captured: dict = {}

    def __init__(self, *a, **k):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False
    async def request(self, method, url, **kw):
        _FakeClient.captured = {"method": method, "url": url, **kw}
        return _FakeResp()


@pytest.mark.asyncio
async def test_get_placeholder_and_query():
    with patch.object(ct, "httpx") as mh:
        mh.AsyncClient = _FakeClient
        out = await ct.call_custom_tool(
            method="GET", url="http://api/{city}/now", headers={"X-Key": "k"},
            arguments={"city": "istanbul", "units": "metric"}, timeout=5,
        )
    assert out == "OK"
    cap = _FakeClient.captured
    assert cap["url"] == "http://api/istanbul/now"   # {city} yerine kondu
    assert cap["params"] == {"units": "metric"}       # kalan arg query'e
    assert cap["headers"] == {"X-Key": "k"}


@pytest.mark.asyncio
async def test_post_body():
    with patch.object(ct, "httpx") as mh:
        mh.AsyncClient = _FakeClient
        await ct.call_custom_tool(method="POST", url="http://api/send", headers=None,
                                  arguments={"to": "a@b.com", "msg": "hi"}, timeout=5)
    cap = _FakeClient.captured
    assert cap["method"] == "POST"
    assert cap["json"] == {"to": "a@b.com", "msg": "hi"}


@pytest.mark.asyncio
async def test_http_error_returns_message():
    class _ErrClient(_FakeClient):
        async def request(self, method, url, **kw):
            return _FakeResp(status=404, text="not found")
    with patch.object(ct, "httpx") as mh:
        mh.AsyncClient = _ErrClient
        out = await ct.call_custom_tool(method="GET", url="http://api/x", headers={}, arguments={}, timeout=5)
    assert "HTTP 404" in out


# ─── runner routing ───

@pytest.mark.asyncio
async def test_runner_routes_custom_tool():
    cfg = AgentConfig(agent_id=uuid.uuid4(), org_id=uuid.uuid4(), name="a", system_prompt="x",
                      provider="openai", model="gpt-4o-mini", temperature=0.7, max_tokens=None,
                      max_steps=5, timeout_seconds=60, tool_names=[], hitl_tool_names=[])
    http = [{"name": "weather", "description": "d", "input_schema": {"type": "object"},
             "method": "GET", "url": "http://api/{city}", "headers": {}, "timeout": 5}]
    runner = AgentRunner(config=cfg, provider=MagicMock(), tracer=MagicMock(), http_tools=http)
    assert runner._http_definitions()[0].name == "weather"
    with patch("app.services.agent.custom_tools.call_custom_tool", new=AsyncMock(return_value="SONUC")) as m:
        out = await runner._execute_tool("weather", {"city": "izmir"})
    assert out == "SONUC"
    assert m.call_args.kwargs["url"] == "http://api/{city}"


# ─── şema doğrulama ───

def test_schema_rejects_reserved_name():
    with pytest.raises(Exception):
        CreateCustomToolRequest(name="web_search", url="http://x")


def test_schema_rejects_bad_name():
    with pytest.raises(Exception):
        CreateCustomToolRequest(name="bad name!", url="http://x")


def test_schema_rejects_bad_method():
    with pytest.raises(Exception):
        CreateCustomToolRequest(name="ok_tool", url="http://x", method="FETCH")


def test_schema_ok():
    t = CreateCustomToolRequest(name="get_weather", url="http://api/{city}", method="get")
    assert t.method == "GET"  # normalize
