"""
Ekip performans istatistikleri — C3

Bir ekibin TeamRun'larından toplu KPI + trend üretir. Saf fonksiyon, canlı hesap.
"""
from __future__ import annotations

from typing import Any


def _duration_ms(run: Any) -> float | None:
    if run.started_at and run.ended_at:
        return (run.ended_at - run.started_at).total_seconds() * 1000
    return None


def compute_team_stats(runs: list[Any]) -> dict:
    total = len(runs)
    completed = [r for r in runs if r.status == "completed"]
    failed = [r for r in runs if r.status == "failed"]
    finished = len(completed) + len(failed)
    durations = [d for r in completed if (d := _duration_ms(r)) is not None]

    ordered = sorted(runs, key=lambda r: r.created_at)
    trend = [
        {
            "run_id": str(r.id),
            "created_at": r.created_at.isoformat(),
            "status": r.status,
            "duration_ms": _duration_ms(r),
        }
        for r in ordered
    ]

    return {
        "total_runs": total,
        "completed_runs": len(completed),
        "failed_runs": len(failed),
        "success_rate": round(len(completed) / finished, 4) if finished else None,
        "avg_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "latest_status": ordered[-1].status if ordered else None,
        "trend": trend,
    }
