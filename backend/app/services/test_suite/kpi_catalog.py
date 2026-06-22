"""
Suite KPI kataloğu — F4.2

Kullanıcının suite başına izlemeyi seçebileceği metriklerin kanonik listesi.
Her anahtar, `suite_stats.compute_suite_stats()` çıktısındaki bir alana birebir
karşılık gelir; `unit` frontend'in nasıl biçimlendireceğini söyler.

NULL kpis → DEFAULT_KPIS gösterilir.
"""
from __future__ import annotations

# unit: percent (0-1 → %) | ms (→ saniye) | usd | score (0-1) | count
KPI_CATALOG: list[dict] = [
    {"key": "success_run_rate", "label": "Başarılı run oranı", "unit": "percent",
     "description": "Tüm case'leri geçen run'ların oranı"},
    {"key": "avg_pass_rate", "label": "Ort. geçme oranı", "unit": "percent",
     "description": "Run'ların case-düzeyi geçme oranı ortalaması"},
    {"key": "latest_pass_rate", "label": "Son geçme oranı", "unit": "percent",
     "description": "En son tamamlanan run'ın geçme oranı"},
    {"key": "avg_latency_ms", "label": "Ort. cevap süresi", "unit": "ms",
     "description": "Run başına ortalama gecikme"},
    {"key": "avg_cost_usd", "label": "Ort. maliyet", "unit": "usd",
     "description": "Run başına ortalama maliyet"},
    {"key": "avg_judge_score", "label": "Ort. judge skoru", "unit": "score",
     "description": "LLM-as-judge ortalaması (çıktı kalitesi dahil)"},
    {"key": "completed_runs", "label": "Tamamlanan run", "unit": "count",
     "description": "Tamamlanmış run sayısı"},
    {"key": "total_runs", "label": "Toplam run", "unit": "count",
     "description": "Tüm run'lar (durumdan bağımsız)"},
]

# Varsayılan görünüm (kpis NULL iken)
DEFAULT_KPIS: list[str] = [
    "success_run_rate",
    "avg_pass_rate",
    "avg_latency_ms",
    "avg_cost_usd",
]

VALID_KPI_KEYS: frozenset[str] = frozenset(item["key"] for item in KPI_CATALOG)


def normalize_kpis(kpis: list[str] | None) -> list[str]:
    """Geçersiz/yinelenen anahtarları ayıkla, katalog sırasını koru. Boş → DEFAULT."""
    if not kpis:
        return list(DEFAULT_KPIS)
    seen = set(kpis)
    ordered = [item["key"] for item in KPI_CATALOG if item["key"] in seen]
    return ordered or list(DEFAULT_KPIS)
