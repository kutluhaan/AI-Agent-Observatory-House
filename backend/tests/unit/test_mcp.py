"""F7.2 — MCP istemci yardımcıları + runner routing birim testleri."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent.base import AgentConfig
from app.services.agent.runner import AgentRunner
from app.services.mcp.client import _content_to_text, _headers


def test_headers_with_and_without_key():
    assert _headers(None) is None
    assert _headers("k") == {"Authorization": "Bearer k"}


def test_content_to_text_joins_text_items():
    result = SimpleNamespace(content=[
        SimpleNamespace(text="hello"),
        SimpleNamespace(text="world"),
    ])
    assert _content_to_text(result) == "hello\nworld"


def test_content_to_text_empty():
    assert _content_to_text(SimpleNamespace(content=[])) == ""


def _runner_with_mcp():
    cfg = AgentConfig(
        agent_id=uuid.uuid4(), org_id=uuid.uuid4(), name="a", system_prompt="x",
        provider="openai", model="gpt-4o-mini", temperature=0.7, max_tokens=None,
        max_steps=5, timeout_seconds=60, tool_names=[], hitl_tool_names=[],
    )
    mcp = [{"name": "search", "description": "d", "input_schema": {"type": "object"},
            "url": "http://mcp:9000/mcp", "api_key": None}]
    return AgentRunner(config=cfg, provider=MagicMock(), tracer=MagicMock(), mcp_tools=mcp)


def test_mcp_definitions_prefixed():
    runner = _runner_with_mcp()
    defs = runner._mcp_definitions()
    assert len(defs) == 1
    assert defs[0].name == "mcp__search"
    assert defs[0].parameters == {"type": "object"}


@pytest.mark.asyncio
async def test_execute_tool_routes_mcp_call():
    runner = _runner_with_mcp()
    with patch("app.services.mcp.client.call_mcp_tool", new=AsyncMock(return_value="RESULT")) as m:
        out = await runner._execute_tool("mcp__search", {"q": "x"})
    assert out == "RESULT"
    m.assert_awaited_once()
    # gerçek MCP tool adı (önek olmadan) iletilmeli
    assert m.call_args.args[2] == "search"


@pytest.mark.asyncio
async def test_execute_tool_mcp_error_is_graceful():
    runner = _runner_with_mcp()
    with patch("app.services.mcp.client.call_mcp_tool", new=AsyncMock(side_effect=RuntimeError("boom"))):
        out = await runner._execute_tool("mcp__search", {})
    assert "MCP tool error" in out
