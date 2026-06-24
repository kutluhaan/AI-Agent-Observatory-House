"""loop it.10 — read_urls (paralel) + read_pdf: doğrulama (ağsız)."""
import uuid

import pytest

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.tools.research import register_research_tools

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reg():
    register_research_tools()


def _ctx():
    return ToolContext(org_id=uuid.uuid4(), trace_id="t", db=None, redis=None)


@pytest.mark.asyncio
async def test_registered():
    assert ToolRegistry.get("read_urls") is not None
    assert ToolRegistry.get("read_pdf") is not None


@pytest.mark.asyncio
async def test_read_urls_empty():
    out = await ToolRegistry.get("read_urls").handler(_ctx(), urls=[])
    assert "error" in out


@pytest.mark.asyncio
async def test_read_pdf_rejects_non_http():
    out = await ToolRegistry.get("read_pdf").handler(_ctx(), url="ftp://x/y.pdf")
    assert "error" in out and "http" in out
