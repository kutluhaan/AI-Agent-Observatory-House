"""
TeamRunner — F8

Bir TeamRun'ı arka planda yürütür: Coordinator agent'ı görevle çalıştırır; o,
`delegate` ile üyelere iş dağıtır, `team_share`/`team_board` ile paylaşılan panoyu
kullanır. Tüm timeline (delegasyon + pano) team_run_messages'a kalıcı yazılır.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.team import Team, TeamRun
from app.services.team.executor import build_member_runner, record_message
from app.services.team.roles import COORDINATOR

logger = structlog.get_logger()


async def _broadcast_status(org_id, run_id) -> None:
    """C2: org kanalına 'değişti' ping'i (frontend run'ı yeniden çeker)."""
    try:
        from app.ws.traces import manager
        await manager.broadcast(str(org_id), {"type": "team_run_updated", "run_id": str(run_id)})
    except Exception:  # noqa: BLE001
        pass


class TeamRunner:
    def __init__(self, run_id: uuid.UUID, db_factory: Any, redis: Any) -> None:
        self.run_id = run_id
        self.db_factory = db_factory
        self.redis = redis

    async def run(self) -> None:
        async with self.db_factory() as db:
            run = (await db.execute(
                select(TeamRun).where(TeamRun.id == self.run_id)
            )).scalar_one_or_none()
            if run is None:
                logger.error("team_runner.run_not_found", run_id=str(self.run_id))
                return

            team = (await db.execute(
                select(Team).where(Team.id == run.team_id).options(selectinload(Team.members))
            )).scalar_one_or_none()
            # üyelerin agent'larını roster için yükle
            members = team.members if team else []
            for m in members:
                await db.refresh(m, ["agent"])

            coordinator = next((m for m in members if m.role == COORDINATOR), None)

            run.status = "running"
            run.started_at = datetime.now(UTC)
            await db.commit()
            await _broadcast_status(run.organization_id, run.id)

            if coordinator is None:
                run.status = "failed"
                run.error_message = "Team has no coordinator member."
                run.ended_at = datetime.now(UTC)
                await db.commit()
                return

            # B3: çok-turlu sohbet — aynı conversation'daki önceki turları history olarak ver
            history: list = []
            if run.conversation_id:
                from app.services.providers.base import Message
                prior = (await db.execute(
                    select(TeamRun).where(
                        TeamRun.conversation_id == run.conversation_id,
                        TeamRun.id != run.id,
                        TeamRun.status == "completed",
                        TeamRun.created_at < run.created_at,
                    ).order_by(TeamRun.created_at.asc())
                )).scalars().all()
                for p in prior:
                    history.append(Message(role="user", content=p.input))
                    history.append(Message(role="assistant", content=p.final_output or ""))

            try:
                runner = await build_member_runner(
                    db, self.redis, coordinator, members,
                    org_id=run.organization_id, team_id=run.team_id, team_run_id=run.id,
                    history=history,
                )
                result = await runner.run(run.input)
                await record_message(db, run.id, "final", result.content, from_role=COORDINATOR, org_id=run.organization_id)
                run.final_output = result.content
                run.status = "completed"
            except Exception as exc:  # noqa: BLE001
                logger.error("team_runner.fatal", run_id=str(run.id), error=str(exc))
                run.status = "failed"
                run.error_message = str(exc)
            run.ended_at = datetime.now(UTC)
            await db.commit()
            await _broadcast_status(run.organization_id, run.id)
            # D: sistem olayı feed'e
            from app.services.notifications.log import log_notification
            _ok = run.status == "completed"
            await log_notification(
                db, run.organization_id, kind="system", level="success" if _ok else "error",
                title=f"Ekip çalıştırması {'tamamlandı' if _ok else 'başarısız'}: {team.name if team else ''}",
                body=(run.final_output or run.error_message or "")[:500], source="team_run",
            )
            logger.info("team_runner.done", run_id=str(run.id), status=run.status)
