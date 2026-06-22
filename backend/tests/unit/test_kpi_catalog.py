"""F4.2 — suite KPI kataloğu birim testleri."""
from app.services.test_suite.kpi_catalog import (
    DEFAULT_KPIS,
    KPI_CATALOG,
    VALID_KPI_KEYS,
    normalize_kpis,
)
from app.services.test_suite.suite_stats import compute_suite_stats


def test_defaults_are_valid_keys():
    assert set(DEFAULT_KPIS).issubset(VALID_KPI_KEYS)


def test_every_catalog_key_exists_in_suite_stats_output():
    """Her KPI anahtarı compute_suite_stats çıktısında bir alana karşılık gelmeli."""
    stats = compute_suite_stats([])  # boş ama tüm anahtarları içerir
    for item in KPI_CATALOG:
        assert item["key"] in stats, f"{item['key']} suite_stats çıktısında yok"
        assert item["unit"] in {"percent", "ms", "usd", "score", "count"}


def test_normalize_empty_returns_defaults():
    assert normalize_kpis(None) == DEFAULT_KPIS
    assert normalize_kpis([]) == DEFAULT_KPIS


def test_normalize_drops_unknown_and_preserves_catalog_order():
    order = [c["key"] for c in KPI_CATALOG]
    # ters sırada + geçersiz anahtar ver
    out = normalize_kpis([order[2], "bogus", order[0]])
    assert "bogus" not in out
    assert out == [order[0], order[2]]  # katalog sırası korunur


def test_normalize_all_invalid_falls_back_to_defaults():
    assert normalize_kpis(["nope", "nada"]) == DEFAULT_KPIS
