"""F1.3 — suite KPI istatistikleri (compute_suite_stats) birim testleri."""
import uuid
from datetime import UTC, datetime, timedelta

from app.services.test_suite.suite_stats import compute_suite_stats


def _run(status, created_offset, summary):
    return type("R", (), {
        "id": uuid.uuid4(),
        "status": status,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=created_offset),
        "summary": summary,
    })()


def test_empty():
    s = compute_suite_stats([])
    assert s["total_runs"] == 0
    assert s["completed_runs"] == 0
    assert s["success_run_rate"] is None
    assert s["trend"] == []


def test_ignores_non_completed_and_summaryless():
    runs = [
        _run("running", 0, None),
        _run("error", 1, None),
        _run("completed", 2, {"pass_rate": 1.0, "avg_latency_ms": 1000}),
    ]
    s = compute_suite_stats(runs)
    assert s["total_runs"] == 3
    assert s["completed_runs"] == 1


def test_success_run_rate_and_averages():
    # 3 tamamlanmış run: pass_rate 1.0, 0.5, 1.0  → 2/3 tam-geçen
    runs = [
        _run("completed", 0, {"pass_rate": 1.0, "avg_latency_ms": 1000, "total_cost_usd": 0.001, "avg_judge_score": 0.9}),
        _run("completed", 1, {"pass_rate": 0.5, "avg_latency_ms": 2000, "total_cost_usd": 0.003}),
        _run("completed", 2, {"pass_rate": 1.0, "avg_latency_ms": 1500, "total_cost_usd": 0.002, "avg_judge_score": 0.8}),
    ]
    s = compute_suite_stats(runs)
    assert s["success_run_rate"] == round(2 / 3, 4)
    assert s["avg_pass_rate"] == round((1.0 + 0.5 + 1.0) / 3, 4)
    assert s["avg_latency_ms"] == 1500           # (1000+2000+1500)/3
    assert s["avg_cost_usd"] == 0.002            # (0.001+0.003+0.002)/3
    assert s["avg_judge_score"] == round((0.9 + 0.8) / 2, 4)  # sadece mevcut olanlar
    assert s["latest_pass_rate"] == 1.0          # en yeni (offset 2)


def test_trend_is_chronological_oldest_first():
    runs = [
        _run("completed", 5, {"pass_rate": 0.7, "avg_latency_ms": 100}),
        _run("completed", 1, {"pass_rate": 0.3, "avg_latency_ms": 100}),
    ]
    s = compute_suite_stats(runs)
    assert [p["pass_rate"] for p in s["trend"]] == [0.3, 0.7]  # eski→yeni
