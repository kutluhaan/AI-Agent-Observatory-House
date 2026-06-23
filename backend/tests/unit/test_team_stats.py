"""C3 — compute_team_stats birim testleri."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.team.team_stats import compute_team_stats

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _run(rid, status, start_offset=None, dur_s=None):
    started = _T0 + timedelta(minutes=start_offset) if start_offset is not None else None
    ended = (started + timedelta(seconds=dur_s)) if (started and dur_s) else None
    return SimpleNamespace(id=rid, status=status, created_at=started or _T0, started_at=started, ended_at=ended)


def test_empty():
    s = compute_team_stats([])
    assert s["total_runs"] == 0
    assert s["success_rate"] is None
    assert s["trend"] == []


def test_success_rate_and_duration():
    runs = [
        _run("r1", "completed", 0, 10),   # 10s
        _run("r2", "completed", 1, 20),   # 20s
        _run("r3", "failed", 2, None),
        _run("r4", "running", 3),
    ]
    s = compute_team_stats(runs)
    assert s["total_runs"] == 4
    assert s["completed_runs"] == 2
    assert s["failed_runs"] == 1
    # bitmiş = 2 completed + 1 failed = 3 → 2/3
    assert s["success_rate"] == round(2 / 3, 4)
    assert s["avg_duration_ms"] == 15000  # (10s+20s)/2
    assert s["latest_status"] == "running"
    assert len(s["trend"]) == 4
