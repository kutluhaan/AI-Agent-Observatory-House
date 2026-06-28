"""
Workflow Scheduler — Faz 5

Her dakika çalışan asyncio loop. Aktif workflow'ların cron trigger'larını
kontrol eder ve zamanı gelen workflow'lar için WorkflowRun oluşturur.
Harici bağımlılık yok — stdlib datetime ile minimal cron eşleştirici.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.workflow import Workflow, WorkflowRun

logger = structlog.get_logger()


# ── Cron matcher (stdlib, 5-field standard format) ─────────────

def _field_matches(field: str, val: int, lo: int, hi: int) -> bool:
    """Returns True if `val` satisfies the cron field expression."""
    for part in field.split(","):
        if part == "*":
            return True
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if base == "*":
                start, end = lo, hi
            elif "-" in base:
                start, end = map(int, base.split("-", 1))
            else:
                start = end = int(base)
            if val in range(start, end + 1, step):
                return True
        elif "-" in part:
            start, end = map(int, part.split("-", 1))
            if start <= val <= end:
                return True
        else:
            if int(part) == val:
                return True
    return False


def cron_matches(expr: str, dt: datetime) -> bool:
    """
    Check if a 5-field cron expression fires at the given datetime (minute precision).
    Fields: minute hour day-of-month month day-of-week (0=Sun, 1=Mon … 6=Sat).
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    # Python weekday(): 0=Mon…6=Sun  →  cron: 0=Sun,1=Mon…6=Sat
    cron_dow = (dt.weekday() + 1) % 7
    return (
        _field_matches(minute, dt.minute, 0, 59)
        and _field_matches(hour, dt.hour, 0, 23)
        and _field_matches(dom, dt.day, 1, 31)
        and _field_matches(month, dt.month, 1, 12)
        and _field_matches(dow, cron_dow, 0, 6)
    )


# ── Scheduler loop ────────────────────────────────────────────

async def run_scheduler() -> None:
    """
    Background task started in app lifespan. Checks cron triggers every 60 s.
    Gracefully exits when cancelled.
    """
    logger.info("workflow_scheduler.started")
    try:
        while True:
            await asyncio.sleep(60)
            try:
                await _tick()
            except Exception as exc:
                logger.error("workflow_scheduler.tick_error", error=str(exc))
    except asyncio.CancelledError:
        logger.info("workflow_scheduler.stopped")


async def _tick() -> None:
    now = datetime.now(UTC)
    minute_start = now.replace(second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Workflow).where(Workflow.status == "active")
        )).scalars().all()

        for wf in rows:
            graph = wf.graph_json or {}
            start_node = next(
                (n for n in graph.get("nodes", [])
                 if n.get("type") == "start"
                 and (n.get("data") or {}).get("trigger_kind") == "schedule"),
                None,
            )
            if not start_node:
                continue

            cron_expr: str = (start_node.get("data") or {}).get("cron", "").strip()
            if not cron_expr:
                continue

            try:
                if not cron_matches(cron_expr, now):
                    continue
            except Exception:
                continue

            # Dedup: skip if already fired this minute
            recent = (await db.execute(
                select(WorkflowRun).where(
                    WorkflowRun.workflow_id == wf.id,
                    WorkflowRun.trigger_kind == "schedule",
                    WorkflowRun.started_at >= minute_start,
                ).limit(1)
            )).scalar_one_or_none()
            if recent is not None:
                continue

            run = WorkflowRun(
                id=uuid.uuid4(),
                workflow_id=wf.id,
                organization_id=wf.organization_id,
                status="running",
                trigger_kind="schedule",
                started_at=now,
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)

            from app.services.workflow.runner import start_workflow_run
            start_workflow_run(wf.id, run.id, wf.organization_id)
            logger.info("workflow_scheduler.fired", workflow_id=str(wf.id), run_id=str(run.id), cron=cron_expr)
