"""
Dashboard Router — F5.2

Org-geneli observability özeti. Canlı hesaplanır (yeni tablo yok); mevcut
compute_suite_stats + compute_agent_stats fonksiyonlarını tekrar kullanır.

Endpoint:
  GET /dashboard   — org overview: sayımlar, birleşik KPI'lar, agent lider tablosu
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.responses import success
from app.models.agent import Agent
from app.models.test_suite import TestCase, TestCaseResult, TestRun, TestSuite
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

    return success(compute_org_dashboard(
        agent_count=agent_count,
        suite_count=int(suite_count),
        runs=list(runs),
        agent_groups=agent_groups,
    ))
