"""
Zaman & Yardımcı tool'ları — Utility kategorisi (loop it.7)

get_current_datetime : şu anki tarih/saat (timezone destekli) — agent'ın "bugün ne" sorununu çözer
date_calculate       : iki tarih arası fark + tarih aritmetiği (X gün/hafta sonrası)
convert_units        : birim çevrimi (uzunluk/ağırlık/sıcaklık/veri) — saf hesap
convert_currency     : döviz çevrimi güncel kurla (Frankfurter/ECB, anahtarsız)

Hepsi anahtarsız/sıfır-config. Tool'lar exception fırlatmaz — hatayı string döner.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from app.services.agent.registry import ToolContext, ToolRegistry

# Aynı kategoride birim tabloları (taban birime oran)
_UNITS: dict[str, dict[str, float]] = {
    "length": {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "ft": 0.3048, "in": 0.0254, "yd": 0.9144},
    "weight": {"kg": 1, "g": 0.001, "mg": 1e-6, "lb": 0.45359237, "oz": 0.0283495231, "t": 1000},
    "data": {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3, "tb": 1024 ** 4},
}
_TEMPS = {"c", "f", "k"}


def register_utility_tools() -> None:
    if "get_current_datetime" in ToolRegistry.all_names():
        return

    @ToolRegistry.register(
        "get_current_datetime",
        "Get the current date and time. Optionally in a specific IANA timezone (e.g. 'Europe/Istanbul', 'UTC').",
        {"type": "object", "properties": {
            "timezone": {"type": "string", "description": "IANA timezone, e.g. 'Europe/Istanbul'. Default 'UTC'."},
        }, "required": []},
    )
    async def get_current_datetime(ctx: ToolContext, timezone: str = "UTC") -> str:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone)
        except Exception:  # noqa: BLE001 — tzdata yok / geçersiz → UTC'ye düş
            from datetime import timezone as _tz
            now = datetime.now(_tz.utc)
            return f"{now.strftime('%Y-%m-%d %H:%M:%S')} UTC (ISO: {now.isoformat()})" + (
                f" [uyarı: '{timezone}' bulunamadı, UTC kullanıldı]" if timezone != "UTC" else "")
        now = datetime.now(tz)
        return f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')} (ISO: {now.isoformat()}) · {now.strftime('%A')}"

    @ToolRegistry.register(
        "date_calculate",
        "Date math. operation='difference' (days between date and date2) or 'add' (date + amount of unit). "
        "Dates are ISO (YYYY-MM-DD or full ISO datetime).",
        {"type": "object", "properties": {
            "operation": {"type": "string", "enum": ["difference", "add"], "description": "'difference' or 'add'."},
            "date": {"type": "string", "description": "Base date, ISO e.g. '2026-06-24'."},
            "date2": {"type": "string", "description": "Second date for 'difference'."},
            "amount": {"type": "integer", "description": "Amount for 'add' (can be negative)."},
            "unit": {"type": "string", "enum": ["days", "weeks", "hours", "minutes"], "description": "Unit for 'add'."},
        }, "required": ["operation", "date"]},
    )
    async def date_calculate(ctx: ToolContext, operation: str, date: str,
                             date2: str | None = None, amount: int = 0, unit: str = "days") -> str:
        try:
            d1 = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return f"[date_calculate error: geçersiz tarih '{date}' (YYYY-MM-DD kullan)]"
        if operation == "difference":
            if not date2:
                return "[date_calculate error: 'difference' için date2 gerekli]"
            try:
                d2 = datetime.fromisoformat(date2.replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                return f"[date_calculate error: geçersiz date2 '{date2}']"
            delta = d2 - d1
            return f"{date} → {date2}: {delta.days} gün ({delta.total_seconds() / 3600:.0f} saat)"
        if operation == "add":
            if unit not in ("days", "weeks", "hours", "minutes"):
                return "[date_calculate error: unit days/weeks/hours/minutes olmalı]"
            result = d1 + timedelta(**{unit: amount})
            return f"{date} {'+' if amount >= 0 else ''}{amount} {unit} = {result.isoformat()} ({result.strftime('%A')})"
        return "[date_calculate error: operation 'difference' veya 'add' olmalı]"

    @ToolRegistry.register(
        "convert_units",
        "Convert between units of the same kind: length (m/km/cm/mm/mi/ft/in/yd), weight (kg/g/mg/lb/oz/t), "
        "data (b/kb/mb/gb/tb), temperature (c/f/k).",
        {"type": "object", "properties": {
            "value": {"type": "number", "description": "Numeric value to convert."},
            "from_unit": {"type": "string", "description": "Source unit, e.g. 'km', 'lb', 'gb', 'c'."},
            "to_unit": {"type": "string", "description": "Target unit, e.g. 'mi', 'kg', 'mb', 'f'."},
        }, "required": ["value", "from_unit", "to_unit"]},
    )
    async def convert_units(ctx: ToolContext, value: float, from_unit: str, to_unit: str) -> str:
        f, t = from_unit.lower().strip(), to_unit.lower().strip()
        if f in _TEMPS and t in _TEMPS:
            c = value if f == "c" else (value - 32) * 5 / 9 if f == "f" else value - 273.15
            out = c if t == "c" else c * 9 / 5 + 32 if t == "f" else c + 273.15
            return f"{value}°{from_unit.upper()} = {round(out, 4)}°{to_unit.upper()}"
        for cat, table in _UNITS.items():
            if f in table and t in table:
                return f"{value} {f} = {round(value * table[f] / table[t], 8)} {t} ({cat})"
        return f"[convert_units error: '{from_unit}' → '{to_unit}' aynı türde değil/desteklenmiyor]"

    @ToolRegistry.register(
        "convert_currency",
        "Convert an amount between currencies at the latest rate (ECB via Frankfurter, no API key). "
        "Use 3-letter codes, e.g. USD, EUR, TRY, GBP.",
        {"type": "object", "properties": {
            "amount": {"type": "number", "description": "Amount to convert."},
            "from_currency": {"type": "string", "description": "Source currency code, e.g. 'USD'."},
            "to_currency": {"type": "string", "description": "Target currency code, e.g. 'TRY'."},
        }, "required": ["amount", "from_currency", "to_currency"]},
    )
    async def convert_currency(ctx: ToolContext, amount: float, from_currency: str, to_currency: str) -> str:
        f, t = from_currency.upper().strip(), to_currency.upper().strip()
        if f == t:
            return f"{amount} {f} = {amount} {t}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get("https://api.frankfurter.dev/v1/latest",
                                     params={"amount": amount, "from": f, "to": t})
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            return f"[convert_currency error: {exc}]"
        rate = (data.get("rates") or {}).get(t)
        if rate is None:
            return f"[convert_currency error: '{f}' → '{t}' desteklenmiyor (kod hatalı olabilir)]"
        return f"{amount} {f} = {rate} {t} (kur tarihi {data.get('date')}, kaynak ECB)"
