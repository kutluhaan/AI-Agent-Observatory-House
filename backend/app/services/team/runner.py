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

            if coordinator is None:
                run.status = "failed"
                run.error_message = "Team has no coordinator member."
                run.ended_at = datetime.now(UTC)
                await db.commit()
                return

            try:
                runner = await build_member_runner(
                    db, self.redis, coordinator, members,
                    org_id=run.organization_id, team_id=run.team_id, team_run_id=run.id,
                )
                result = await runner.run(run.input)
                await record_message(db, run.id, "final", result.content, from_role=COORDINATOR)
                run.final_output = result.content
                run.status = "completed"
            except Exception as exc:  # noqa: BLE001
                logger.error("team_runner.fatal", run_id=str(run.id), error=str(exc))
                run.status = "failed"
                run.error_message = str(exc)
            run.ended_at = datetime.now(UTC)
            await db.commit()
            logger.info("team_runner.done", run_id=str(run.id), status=run.status)
