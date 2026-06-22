"""F5.1 — compute_agent_stats birim testleri."""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.test_suite.agent_stats import compute_agent_stats


@dataclass
class _Row:
    run_id: str
    status: str
    latency_ms: int | None = None
    cost_usd: float | None = None
    total_tokens: int | None = None
    judge_results: list | None = None
    rag_metrics: dict | None = None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=UTC))


def test_empty_returns_none_metrics_with_keys():
    s = compute_agent_stats([])
    assert s["total_cases"] == 0
    assert s["pass_rate"] is None
    assert s["runs_count"] == 0
    assert s["trend"] == []


def test_aggregates_pass_rate_and_means():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        _Row("r1", "passed", latency_ms=100, cost_usd=0.001, total_tokens=10,
             judge_results=[{"type": "output_quality", "score": 0.8}], created_at=t0),
        _Row("r1", "failed", latency_ms=300, cost_usd=0.003, total_tokens=30,
             judge_results=[{"type": "output_quality", "score": 0.4}], created_at=t0),
    ]
    s = compute_agent_stats(rows)
    assert s["total_cases"] == 2
    assert s["passed_cases"] == 1
    assert s["pass_rate"] == 0.5
    assert s["avg_latency_ms"] == 200
    assert s["avg_judge_score"] == 0.6
    assert s["total_tokens"] == 40
    assert s["runs_count"] == 1


def test_trend_grouped_by_run_and_sorted():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(days=1)
    rows = [
        _Row("r2", "passed", latency_ms=100, created_at=t1),  # daha yeni
        _Row("r1", "failed", latency_ms=200, created_at=t0),  # daha eski
        _Row("r1", "passed", latency_ms=200, created_at=t0),
    ]
    s = compute_agent_stats(rows)
    assert s["runs_count"] == 2
    assert [p["run_id"] for p in s["trend"]] == ["r1", "r2"]  # eski → yeni
    assert s["trend"][0]["pass_rate"] == 0.5  # r1: 1/2
    assert s["trend"][1]["pass_rate"] == 1.0  # r2: 1/1


def test_rag_none_when_no_rag_metrics():
    s = compute_agent_stats([_Row("r1", "passed")])
    assert s["rag"] is None


def test_rag_aggregates_and_trends():
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = t0 + timedelta(days=1)
    rows = [
        _Row("r1", "passed", rag_metrics={"faithfulness": 0.8, "answer_relevancy": 0.9,
                                          "context_recall": 0.7, "context_precision": 0.6}, created_at=t0),
        _Row("r2", "passed", rag_metrics={"faithfulness": 1.0, "answer_relevancy": 0.8,
                                          "context_recall": 0.9, "context_precision": 0.8}, created_at=t1),
        _Row("r2", "failed", created_at=t1),  # RAG'siz → sayılmaz
    ]
    s = compute_agent_stats(rows)
    assert s["rag"] is not None
    assert s["rag"]["cases_with_rag"] == 2
    assert s["rag"]["faithfulness"] == 0.9  # (0.8 + 1.0)/2
    assert [p["run_id"] for p in s["rag"]["trend"]] == ["r1", "r2"]
    assert s["rag"]["trend"][1]["faithfulness"] == 1.0
