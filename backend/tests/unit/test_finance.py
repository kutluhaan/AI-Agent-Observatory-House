"""D/#2 — Finans tool'ları: teknik indikatör matematiği (saf, deterministik)."""
import pytest

from app.services.agent.tools.finance import _ema, _macd, _rsi, _sma, register_finance_tools
from app.services.agent.registry import ToolRegistry

pytestmark = pytest.mark.unit


def test_sma():
    assert _sma([1, 2, 3, 4, 5], 3) == 4.0      # (3+4+5)/3
    assert _sma([1, 2], 5) is None               # yetersiz veri


def test_ema_constant_series():
    # Sabit seride EMA = sabit değer
    assert _ema([5.0] * 10, 5) == 5.0
    assert _ema([1, 2], 5) is None


def test_rsi_extremes():
    assert _rsi(list(range(1, 30))) == 100.0     # hep artış → 100
    assert _rsi(list(range(30, 1, -1))) == 0.0   # hep azalış → 0
    assert _rsi([1, 2, 3]) is None               # yetersiz veri


def test_rsi_mixed_in_range():
    closes = [10, 11, 10.5, 11.5, 11, 12, 11.5, 12.5, 12, 13, 12.5, 13.5, 13, 14, 13.5, 14.5]
    rsi = _rsi(closes)
    assert rsi is not None and 0 < rsi < 100      # karışık → 0-100 arası


def test_macd_shape():
    closes = [float(x) for x in range(1, 60)]     # yeterli veri
    macd = _macd(closes)
    assert macd is not None and len(macd) == 3
    line, signal, hist = macd
    assert abs(hist - (line - signal)) < 1e-6      # histogram = line - signal


def test_macd_insufficient_data():
    assert _macd([1.0, 2.0, 3.0]) is None


def test_finance_tools_registered():
    register_finance_tools()
    for name in ("get_crypto_price", "get_crypto_ohlc", "get_stock_quote",
                 "get_stock_history", "get_technical_indicators", "get_market_news"):
        assert ToolRegistry.get(name) is not None
