"""
Finance Tools — D/#2 (finans kategorisi)

Anahtarsız/ucuz public kaynaklarla piyasa verisi + teknik analiz. Trading ekibinin
temeli. GERÇEK EMİR YOK — yalnız veri/analiz (güvenli; kullanıcı "sadece analiz" seçti).

  get_crypto_price        : anlık kripto fiyatı + 24s değişim (CoinGecko, anahtarsız)
  get_crypto_ohlc         : günlük OHLC geçmişi (CoinGecko)
  get_stock_quote         : anlık hisse fiyatı (Stooq, anahtarsız)
  get_stock_history       : günlük OHLC geçmişi (Stooq)
  get_technical_indicators: RSI / SMA / EMA / MACD (fiyat geçmişinden hesaplar — ek API yok)
  get_market_news         : bir sembol/konu için güncel finans haberi (Tavily, web_search üstüne)

Tüm tool'lar exception fırlatmaz — hatayı string döner (AgentRunner uyumlu).
"""
from __future__ import annotations

import httpx
import structlog

from app.services.agent.registry import ToolContext, ToolRegistry

logger = structlog.get_logger()

_TIMEOUT = 15.0
_UA = "Mozilla/5.0 (compatible; ObservatoryFinanceBot/1.0)"
_COINGECKO = "https://api.coingecko.com/api/v3"


# ─── Teknik indikatör hesapları (saf Python) ───────────────

def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    out = [ema]
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
        out.append(ema)
    return out


def _ema(values: list[float], period: int) -> float | None:
    s = _ema_series(values, period)
    return s[-1] if s else None


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period + 1, len(values)):
        d = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(d, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0.0)) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _macd(values: list[float]) -> tuple[float, float, float] | None:
    """MACD(12,26,9) → (macd_line, signal, histogram). Yetersiz veri → None."""
    e12, e26 = _ema_series(values, 12), _ema_series(values, 26)
    if not e12 or not e26:
        return None
    n = min(len(e12), len(e26))
    macd_line_series = [e12[-n + i] - e26[-n + i] for i in range(n)]
    macd_line = macd_line_series[-1]
    signal_series = _ema_series(macd_line_series, 9)
    if not signal_series:
        return None
    signal = signal_series[-1]
    return round(macd_line, 4), round(signal, 4), round(macd_line - signal, 4)


# ─── Veri çekiciler ────────────────────────────────────────

async def _coingecko_market(symbol: str) -> dict | None:
    """CoinGecko /coins/markets — sembolden ilk eşleşen coini döner."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as c:
        r = await c.get(f"{_COINGECKO}/coins/markets", params={
            "vs_currency": "usd", "symbols": symbol.lower(), "per_page": 1,
        })
        r.raise_for_status()
        data = r.json()
    return data[0] if data else None


async def _crypto_closes(symbol: str, days: int) -> tuple[str, list[float]] | None:
    """(coin_id, GÜNLÜK kapanış fiyatları) — market_chart'tan günlük downsample."""
    market = await _coingecko_market(symbol)
    if not market:
        return None
    coin_id = market["id"]
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as c:
        r = await c.get(f"{_COINGECKO}/coins/{coin_id}/market_chart",
                        params={"vs_currency": "usd", "days": days})
        r.raise_for_status()
        prices = r.json().get("prices", [])  # [[ms_ts, price], ...] (saatlik)
    # Güne göre grupla → her günün son fiyatı = günlük kapanış
    by_day: dict[int, float] = {}
    for ts_ms, price in prices:
        by_day[int(ts_ms) // 86_400_000] = float(price)
    closes = [by_day[d] for d in sorted(by_day)]
    return coin_id, closes


# ─── Yahoo Finance (anahtarsız, JSON) — hisse senedi ───────

_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart"


async def _yahoo_chart(symbol: str, range_: str) -> dict | None:
    """Yahoo chart sonucu (meta + timestamp + ohlc dizileri) ya da None."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as c:
        r = await c.get(f"{_YAHOO}/{symbol.upper()}", params={"range": range_, "interval": "1d"})
        r.raise_for_status()
        chart = r.json().get("chart", {})
    if chart.get("error") or not chart.get("result"):
        return None
    return chart["result"][0]


async def _stock_closes(symbol: str, range_: str = "6mo") -> list[float]:
    res = await _yahoo_chart(symbol, range_)
    if not res:
        return []
    quote = (res.get("indicators", {}).get("quote") or [{}])[0]
    return [float(c) for c in (quote.get("close") or []) if c is not None]


# ─── Registration ──────────────────────────────────────────

def register_finance_tools() -> None:
    """Idempotent — birden fazla çağrılabilir."""
    try:
        ToolRegistry.get("get_crypto_price")
        return
    except KeyError:
        pass

    @ToolRegistry.register(
        name="get_crypto_price",
        description="Get the current USD price and 24h change for a cryptocurrency by symbol (e.g. BTC, ETH). Source: CoinGecko (no API key).",
        parameters={"type": "object", "properties": {
            "symbol": {"type": "string", "description": "Crypto symbol, e.g. 'BTC', 'ETH', 'SOL'."},
        }, "required": ["symbol"]},
    )
    async def get_crypto_price(ctx: ToolContext, symbol: str) -> str:
        try:
            m = await _coingecko_market(symbol)
        except Exception as exc:  # noqa: BLE001
            return f"[get_crypto_price error: {exc}]"
        if not m:
            return f"[get_crypto_price: '{symbol}' bulunamadı]"
        chg = m.get("price_change_percentage_24h")
        chg_s = f"{chg:+.2f}%" if chg is not None else "?"
        return (f"{m['name']} ({m['symbol'].upper()}): ${m['current_price']:,} · 24s {chg_s} · "
                f"24s aralık ${m.get('low_24h')}–${m.get('high_24h')} · "
                f"hacim ${m.get('total_volume'):,} · piyasa değeri ${m.get('market_cap'):,}")

    @ToolRegistry.register(
        name="get_crypto_ohlc",
        description="Get daily OHLC (open/high/low/close) price history for a crypto symbol over the last N days (1-365). Source: CoinGecko.",
        parameters={"type": "object", "properties": {
            "symbol": {"type": "string", "description": "Crypto symbol, e.g. 'BTC'."},
            "days": {"type": "integer", "description": "Days of history (1-365). Default 30.", "default": 30},
        }, "required": ["symbol"]},
    )
    async def get_crypto_ohlc(ctx: ToolContext, symbol: str, days: int = 30) -> str:
        days = max(1, min(365, days))
        try:
            res = await _crypto_closes(symbol, days)
        except Exception as exc:  # noqa: BLE001
            return f"[get_crypto_ohlc error: {exc}]"
        if not res:
            return f"[get_crypto_ohlc: '{symbol}' bulunamadı]"
        _, closes = res
        if not closes:
            return f"[get_crypto_ohlc: '{symbol}' için veri yok]"
        first, last = closes[0], closes[-1]
        chg = (last - first) / first * 100 if first else 0
        return (f"{symbol.upper()} son {len(closes)} kapanış: ilk ${first:,.4g} → son ${last:,.4g} "
                f"({chg:+.2f}%) · min ${min(closes):,.4g} · max ${max(closes):,.4g}")

    @ToolRegistry.register(
        name="get_stock_quote",
        description="Get the latest daily quote (OHLC + volume) for a stock ticker (e.g. AAPL, MSFT). US assumed if no suffix. Source: Stooq (no API key).",
        parameters={"type": "object", "properties": {
            "symbol": {"type": "string", "description": "Ticker, e.g. 'AAPL'. Non-US: append market, e.g. 'vow.de'."},
        }, "required": ["symbol"]},
    )
    async def get_stock_quote(ctx: ToolContext, symbol: str) -> str:
        try:
            res = await _yahoo_chart(symbol, "5d")
        except Exception as exc:  # noqa: BLE001
            return f"[get_stock_quote error: {exc}]"
        if not res:
            return f"[get_stock_quote: '{symbol}' bulunamadı (sembolü kontrol et)]"
        meta = res.get("meta", {})
        price = meta.get("regularMarketPrice")
        cur = meta.get("currency", "USD")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        chg = ((price - prev) / prev * 100) if (price and prev) else None
        chg_s = f"{chg:+.2f}%" if chg is not None else "?"
        return (f"{meta.get('symbol', symbol.upper())}: {price} {cur} · "
                f"önceki kapanış {prev} · değişim {chg_s}")

    @ToolRegistry.register(
        name="get_stock_history",
        description="Get recent daily closing prices for a stock ticker over the last N days (summary). Source: Stooq.",
        parameters={"type": "object", "properties": {
            "symbol": {"type": "string", "description": "Ticker, e.g. 'AAPL'."},
            "days": {"type": "integer", "description": "Trading days to summarize (5-250). Default 30.", "default": 30},
        }, "required": ["symbol"]},
    )
    async def get_stock_history(ctx: ToolContext, symbol: str, days: int = 30) -> str:
        days = max(5, min(250, days))
        rng = "1mo" if days <= 21 else "3mo" if days <= 63 else "6mo" if days <= 126 else "1y"
        try:
            closes = await _stock_closes(symbol, rng)
        except Exception as exc:  # noqa: BLE001
            return f"[get_stock_history error: {exc}]"
        if not closes:
            return f"[get_stock_history: '{symbol}' için veri yok]"
        closes = closes[-days:]
        first, last = closes[0], closes[-1]
        chg = (last - first) / first * 100 if first else 0
        return (f"{symbol.upper()} son {len(closes)} işlem günü: {first:.2f} → {last:.2f} "
                f"({chg:+.2f}%) · min {min(closes):.2f} · max {max(closes):.2f}")

    @ToolRegistry.register(
        name="get_technical_indicators",
        description=("Compute technical indicators (RSI-14, SMA-20/50, EMA-12/26, MACD) from recent price history. "
                     "Set asset_type to 'crypto' or 'stock'. Returns a concise signal summary."),
        parameters={"type": "object", "properties": {
            "symbol": {"type": "string", "description": "Crypto symbol (BTC) or stock ticker (AAPL)."},
            "asset_type": {"type": "string", "enum": ["crypto", "stock"], "description": "'crypto' or 'stock'."},
        }, "required": ["symbol", "asset_type"]},
    )
    async def get_technical_indicators(ctx: ToolContext, symbol: str, asset_type: str) -> str:
        try:
            if asset_type == "crypto":
                res = await _crypto_closes(symbol, 120)
                closes = res[1] if res else []
            else:
                closes = await _stock_closes(symbol, "6mo")
        except Exception as exc:  # noqa: BLE001
            return f"[get_technical_indicators error: {exc}]"
        if len(closes) < 27:
            return f"[get_technical_indicators: '{symbol}' için yeterli geçmiş yok ({len(closes)} nokta)]"
        rsi = _rsi(closes)
        sma20, sma50 = _sma(closes, 20), _sma(closes, 50)
        ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
        macd = _macd(closes)
        rsi_note = "aşırı alım" if rsi and rsi >= 70 else "aşırı satım" if rsi and rsi <= 30 else "nötr"
        parts = [f"{symbol.upper()} ({asset_type}) — son fiyat ${closes[-1]:,.4g}",
                 f"RSI-14: {rsi} ({rsi_note})",
                 f"SMA-20: {sma20:,.4g}" if sma20 else "SMA-20: —",
                 f"SMA-50: {sma50:,.4g}" if sma50 else "SMA-50: —",
                 f"EMA-12: {ema12:,.4g}" if ema12 else "EMA-12: —",
                 f"EMA-26: {ema26:,.4g}" if ema26 else "EMA-26: —"]
        if macd:
            trend = "yükseliş" if macd[2] > 0 else "düşüş"
            parts.append(f"MACD: {macd[0]} / sinyal {macd[1]} / histogram {macd[2]} ({trend})")
        return " · ".join(parts)

    @ToolRegistry.register(
        name="get_market_news",
        description="Get recent financial news for a symbol or topic (e.g. 'BTC outlook', 'AAPL earnings'). Uses web search, news-focused.",
        parameters={"type": "object", "properties": {
            "query": {"type": "string", "description": "News query, e.g. 'Bitcoin price outlook' or 'NVDA earnings'."},
            "max_results": {"type": "integer", "description": "Results (1-10). Default 5.", "default": 5},
        }, "required": ["query"]},
    )
    async def get_market_news(ctx: ToolContext, query: str, max_results: int = 5) -> str:
        from app.services.agent.tools.research import _web_search
        try:
            return await _web_search(ctx, query, max_results, "news", "week")
        except Exception as exc:  # noqa: BLE001
            return f"[get_market_news error: {exc}]"

    logger.info("finance.tools_registered")
