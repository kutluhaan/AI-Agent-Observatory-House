"""F5.2 — compute_org_dashboard birim testleri."""
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.services.test_suite.org_dashboard import compute_org_dashboard


@dataclass
class _Run:
    id: str
    status: str
    summary: dict | None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=UTC))


@dataclass
class _Res:
    run_id: str
    status: str
    latency_ms: int | None = None
    cost_usd: float | None = None
    total_tokens: int | None = None
    judge_results: list | None = None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=UTC))


def test_empty_org():
    d = compute_org_dashboard(agent_count=0, suite_count=0, runs=[], agent_groups=[])
    assert d["counts"]["agents"] == 0
    assert d["leaderboard"] == []
    assert d["success_run_rate"] is None


def test_counts_and_leaderboard_sorted():
    runs = [
        _Run("r1", "completed", {"pass_rate": 1.0, "avg_latency_ms": 100, "total_cost_usd": 0.001}),
        _Run("r2", "completed", {"pass_rate": 0.5, "avg_latency_ms": 200, "total_cost_usd": 0.002}),
    ]
    agent_groups = [
        {"agent_id": "a-weak", "name": "Weak", "rows": [_Res("r1", "failed"), _Res("r1", "passed")]},
        {"agent_id": "a-strong", "name": "Strong", "rows": [_Res("r2", "passed"), _Res("r2", "passed")]},
        {"agent_id": "a-empty", "name": "Empty", "rows": []},  # atlanmalı
    ]
    d = compute_org_dashboard(agent_count=3, suite_count=2, runs=runs, agent_groups=agent_groups)

    assert d["counts"]["agents"] == 3
    assert d["counts"]["suites"] == 2
    assert d["counts"]["total_runs"] == 2
    # success_run_rate: pass_rate==1.0 olan 1/2 = 0.5
    assert d["success_run_rate"] == 0.5
    # leaderboard: boş agent atlandı, en iyi (Strong 1.0) önce
    assert d["agents_evaluated"] == 2
    assert d["leaderboard"][0]["name"] == "Strong"
    assert d["leaderboard"][0]["pass_rate"] == 1.0
    assert d["leaderboard"][1]["name"] == "Weak"
