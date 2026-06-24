"""loop it.7 — Zaman & Yardımcı tool'ları: çevrim + tarih matematiği (saf, deterministik)."""
import uuid

import pytest

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.agent.tools.utility import register_utility_tools

pytestmark = pytest.mark.unit


def _ctx():
    return ToolContext(org_id=uuid.uuid4(), trace_id="t", db=None, redis=None)


@pytest.fixture(autouse=True)
def _reg():
    register_utility_tools()


async def _call(name, **kw):
    return await ToolRegistry.get(name).handler(_ctx(), **kw)


@pytest.mark.asyncio
async def test_convert_units_length_and_temperature():
    assert "1000" in await _call("convert_units", value=1, from_unit="km", to_unit="m")
    r = await _call("convert_units", value=0, from_unit="c", to_unit="f")
    assert "32" in r  # 0°C = 32°F
    bad = await _call("convert_units", value=1, from_unit="km", to_unit="kg")
    assert "error" in bad  # farklı tür


@pytest.mark.asyncio
async def test_date_calculate():
    diff = await _call("date_calculate", operation="difference", date="2026-01-01", date2="2026-01-11")
    assert "10 gün" in diff
    add = await _call("date_calculate", operation="add", date="2026-01-01", amount=7, unit="days")
    assert "2026-01-08" in add
    bad = await _call("date_calculate", operation="difference", date="2026-01-01")
    assert "error" in bad  # date2 yok


@pytest.mark.asyncio
async def test_get_current_datetime_runs():
    out = await _call("get_current_datetime")
    assert "ISO:" in out  # UTC formatı


@pytest.mark.asyncio
async def test_convert_currency_same_code_no_network():
    out = await _call("convert_currency", amount=100, from_currency="USD", to_currency="USD")
    assert "100" in out and "USD" in out
