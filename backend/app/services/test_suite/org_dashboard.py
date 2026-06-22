"""
Org-geneli dashboard — F5.2

Bir org'un tüm test aktivitesinden üst-düzey özet üretir. Canlı hesaplanır
(yeni tablo yok); mevcut compute_suite_stats + compute_agent_stats saf
fonksiyonlarını tekrar kullanır.
"""
from __future__ import annotations

from typing import Any

from app.services.test_suite.agent_stats import compute_agent_stats
from app.services.test_suite.suite_stats import compute_suite_stats


def compute_org_dashboard(
    *,
    agent_count: int,
    suite_count: int,
    runs: list[Any],
    agent_groups: list[dict],
) -> dict:
    """
    agent_groups: [{"agent_id": str, "name": str, "rows": [TestCaseResult-benzeri]}]
                  — lider tablosu için agent başına case sonuçları.
    runs: org'un tüm TestRun'ları (compute_suite_stats org düzeyinde uygulanır).
    """
    run_stats = compute_suite_stats(runs)

    leaderboard = []
    for g in agent_groups:
        if not g["rows"]:
            continue
        s = compute_agent_stats(g["rows"])
        leaderboard.append({
            "agent_id": g["agent_id"],
            "name": g["name"],
            "pass_rate": s["pass_rate"],
            "avg_judge_score": s["avg_judge_score"],
            "avg_latency_ms": s["avg_latency_ms"],
            "total_cases": s["total_cases"],
        })
    # En iyi → en kötü (pass_rate, sonra judge skoru); None'lar sona
    leaderboard.sort(
        key=lambda a: (
            a["pass_rate"] if a["pass_rate"] is not None else -1.0,
            a["avg_judge_score"] if a["avg_judge_score"] is not None else -1.0,
        ),
        reverse=True,
    )

    return {
        "counts": {
            "agents": agent_count,
            "suites": suite_count,
            "total_runs": run_stats["total_runs"],
            "completed_runs": run_stats["completed_runs"],
        },
        "success_run_rate": run_stats["success_run_rate"],
        "avg_pass_rate": run_stats["avg_pass_rate"],
        "avg_latency_ms": run_stats["avg_latency_ms"],
        "avg_cost_usd": run_stats["avg_cost_usd"],
        "avg_judge_score": run_stats["avg_judge_score"],
        "trend": run_stats["trend"],
        "agents_evaluated": len(leaderboard),
        "leaderboard": leaderboard,
    }
