"""
Dashboard Router — F5.2

Org-geneli observability özeti. Canlı hesaplanır (yeni tablo yok); mevcut
compute_suite_stats + compute_agent_stats fonksiyonlarını tekrar kullanır.

Endpoint:
  GET /dashboard   — org overview: sayımlar, birleşik KPI'lar, agent lider tablosu
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.responses import success
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.models.team import Team, TeamRun
from app.models.test_suite import TestCase, TestCaseResult, TestRun, TestSuite
from app.services.team.team_stats import compute_team_stats
from app.services.test_suite.org_dashboard import compute_org_dashboard

router = APIRouter()


@router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    org_id = ctx.org_id

    agents = (await db.execute(
        select(Agent).where(Agent.organization_id == org_id)
    )).scalars().all()
    agent_name = {a.id: a.name for a in agents}
    agent_count = sum(1 for a in agents if a.is_active)

    suite_count = (await db.execute(
        select(func.count()).select_from(TestSuite).where(TestSuite.organization_id == org_id)
    )).scalar() or 0

    runs = (await db.execute(
        select(TestRun).where(TestRun.organization_id == org_id)
    )).scalars().all()

    # Lider tablosu için agent başına case sonuçları
    rows = (await db.execute(
        select(TestCaseResult, TestCase.agent_id)
        .join(TestCase, TestCaseResult.case_id == TestCase.id)
        .join(TestRun, TestCaseResult.run_id == TestRun.id)
        .where(TestRun.organization_id == org_id)
    )).all()

    groups: dict = {}
    for result, agent_id in rows:
        if agent_id is None:
            continue
        groups.setdefault(agent_id, []).append(result)

    agent_groups = [
        {"agent_id": str(aid), "name": agent_name.get(aid, "—"), "rows": rs}
        for aid, rs in groups.items()
    ]

    overview = compute_org_dashboard(
        agent_count=agent_count,
        suite_count=int(suite_count),
        runs=list(runs),
        agent_groups=agent_groups,
    )

    # ── Günlük aktivite (son 14 gün) ─────────────────────────
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    daily: dict = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    for run in runs:
        if not run.created_at:
            continue
        run_dt = run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=timezone.utc)
        if run_dt < cutoff:
            continue
        day = run_dt.strftime("%Y-%m-%d")
        daily[day]["total"] += 1
        summary = run.summary or {}
        if run.status == "completed" and (summary.get("pass_rate") or 0) >= 1.0:
            daily[day]["passed"] += 1
        elif run.status in ("failed", "error"):
            daily[day]["failed"] += 1
    overview["daily_activity"] = sorted(
        [{"day": k, **v} for k, v in daily.items()], key=lambda x: x["day"]
    )

    # ── Agent kullanım sıklığı (case çalıştırma sayısı) ──────
    usage: dict = {}
    for result, agent_id in rows:
        if agent_id is None:
            continue
        key = str(agent_id)
        if key not in usage:
            usage[key] = {"runs": 0, "total_lat": 0.0, "n": 0, "name": agent_name.get(agent_id, "—")}
        usage[key]["runs"] += 1
        if result.latency_ms is not None:
            usage[key]["total_lat"] += float(result.latency_ms)
            usage[key]["n"] += 1
    overview["agent_usage"] = sorted(
        [
            {
                "agent_id": k,
                "name": v["name"],
                "runs": v["runs"],
                "avg_latency_ms": round(v["total_lat"] / v["n"]) if v["n"] > 0 else None,
            }
            for k, v in usage.items()
        ],
        key=lambda x: x["runs"],
        reverse=True,
    )[:10]

    # ── Gecikme dağılımı ─────────────────────────────────────
    lat_buckets: Counter = Counter()
    for result, _ in rows:
        if result.latency_ms is None:
            continue
        ms = result.latency_ms
        if ms < 1000:
            lat_buckets["<1s"] += 1
        elif ms < 3000:
            lat_buckets["1-3s"] += 1
        elif ms < 10000:
            lat_buckets["3-10s"] += 1
        else:
            lat_buckets[">10s"] += 1
    overview["latency_dist"] = [
        {"bucket": b, "count": lat_buckets.get(b, 0)}
        for b in ["<1s", "1-3s", "3-10s", ">10s"]
    ]

    # C4: ekip lider tablosu — her ekibin run'larından performans
    teams = (await db.execute(
        select(Team).where(Team.organization_id == org_id).options(selectinload(Team.members))
    )).scalars().all()
    team_runs = (await db.execute(
        select(TeamRun).where(TeamRun.organization_id == org_id)
    )).scalars().all()
    runs_by_team: dict = {}
    for r in team_runs:
        runs_by_team.setdefault(r.team_id, []).append(r)

    team_board = []
    for t in teams:
        st = compute_team_stats(runs_by_team.get(t.id, []))
        team_board.append({
            "team_id": str(t.id),
            "name": t.name,
            "members": len(t.members),
            "total_runs": st["total_runs"],
            "success_rate": st["success_rate"],
            "avg_duration_ms": st["avg_duration_ms"],
        })
    # En çok çalıştırılan + başarılı önce
    team_board.sort(key=lambda x: (x["success_rate"] or -1, x["total_runs"]), reverse=True)

    overview["counts"]["teams"] = len(teams)
    overview["teams_evaluated"] = sum(1 for t in team_board if t["total_runs"] > 0)
    overview["team_leaderboard"] = team_board
    return success(overview)
