"""
Model fiyatlandırma — token kullanımından yaklaşık USD maliyet tahmini.

Fiyatlar 1M token başına (girdi, çıktı) USD; Haziran 2026 kamuya açık liste
fiyatlarına yakın *tahminlerdir*. Maliyet "estimated" olarak etiketlenmeli.
Provider'lar usage'ı {prompt_tokens, completion_tokens} olarak normalize eder.
"""
from __future__ import annotations

# model anahtarı → (input $/1M, output $/1M). Eşleşme: önce tam, sonra en uzun prefix.
_PRICES: dict[str, tuple[float, float]] = {
    # Google Gemini
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-1.5-flash": (0.075, 0.30),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4.1": (2.0, 8.0),
    "o3-mini": (1.10, 4.40),
    # Anthropic
    "claude-opus": (5.0, 25.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (1.0, 5.0),
    # Ollama (yerel) — maliyetsiz
    "llama": (0.0, 0.0),
    "qwen": (0.0, 0.0),
    "mistral": (0.0, 0.0),
}

# Provider bazlı yedek oran (model eşleşmezse)
_PROVIDER_FALLBACK: dict[str, tuple[float, float]] = {
    "gemini": (0.30, 2.50),
    "openai": (2.50, 10.0),
    "anthropic": (3.0, 15.0),
    "ollama": (0.0, 0.0),
}

_GLOBAL_FALLBACK = (1.0, 5.0)


def _rates(provider: str, model: str) -> tuple[float, float]:
    m = (model or "").lower()
    # En uzun prefix eşleşmesi
    best: str | None = None
    for key in _PRICES:
        if m == key or m.startswith(key):
            if best is None or len(key) > len(best):
                best = key
    if best is not None:
        return _PRICES[best]
    return _PROVIDER_FALLBACK.get((provider or "").lower(), _GLOBAL_FALLBACK)


def estimate_cost(provider: str, model: str, usage: dict | None) -> float | None:
    """Token kullanımından yaklaşık USD maliyet. usage yoksa None."""
    if not usage:
        return None
    in_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    out_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    if in_tokens == 0 and out_tokens == 0:
        return None
    in_rate, out_rate = _rates(provider, model)
    cost = (in_tokens / 1_000_000) * in_rate + (out_tokens / 1_000_000) * out_rate
    return round(cost, 6)
