"""
Suite KPI istatistikleri — F1.3

Bir suite'in tamamlanmış run'larından (DB'de kalıcı) toplu KPI'lar + trend üretir.
Saf fonksiyon: TestRun benzeri nesnelerin listesini alır, dict döner.

Tanımlar:
  success_run_rate — run-düzeyi başarı: pass_rate == 1.0 olan (tüm case'leri
                     geçen) run'ların oranı. Kullanıcının "successful run rate"i.
  avg_pass_rate    — case-düzeyi başarı: run'ların pass_rate ortalaması.
  avg_latency_ms   — "cevap verme süresi" KPI: run'ların ortalama gecikme ort.
"""
from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def compute_suite_stats(runs: list[Any]) -> dict:
    """runs: TestRun benzeri (.id, .status, .created_at, .summary) — herhangi sırada."""
    completed = sorted(
        [r for r in runs if r.status == "completed" and r.summary],
        key=lambda r: r.created_at,
    )

    pass_rates = [float(r.summary.get("pass_rate") or 0.0) for r in completed]
    latencies = [float(r.summary["avg_latency_ms"]) for r in completed if r.summary.get("avg_latency_ms") is not None]
    costs = [float(r.summary["total_cost_usd"]) for r in completed if r.summary.get("total_cost_usd") is not None]
    judge_scores = [float(r.summary["avg_judge_score"]) for r in completed if r.summary.get("avg_judge_score") is not None]

    success_runs = sum(1 for pr in pass_rates if pr >= 1.0)

    trend = [
        {
            "run_id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "pass_rate": r.summary.get("pass_rate"),
            "avg_latency_ms": r.summary.get("avg_latency_ms"),
            "total_cost_usd": r.summary.get("total_cost_usd"),
            "total_tokens": r.summary.get("total_tokens"),
            "avg_judge_score": r.summary.get("avg_judge_score"),
        }
        for r in completed
    ]

    avg_latency = _mean(latencies)
    return {
        "total_runs": len(runs),
        "completed_runs": len(completed),
        "success_run_rate": round(success_runs / len(completed), 4) if completed else None,
        "avg_pass_rate": _mean(pass_rates),
        "latest_pass_rate": completed[-1].summary.get("pass_rate") if completed else None,
        "avg_latency_ms": round(avg_latency) if avg_latency is not None else None,
        "avg_cost_usd": _mean(costs),
        "avg_judge_score": _mean(judge_scores),
        "trend": trend,
    }
