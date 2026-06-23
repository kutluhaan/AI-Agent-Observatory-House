"""
Teams Router — F8 (Agent ekipleri)

  GET    /teams/roles               — rol kataloğu (etiket + varsayılan prompt)
  POST   /teams                     — ekip oluştur (admin)
  GET    /teams                     — listele (member)
  GET    /teams/{id}                — detay (member)
  PATCH  /teams/{id}                — güncelle (admin)
  DELETE /teams/{id}                — sil (admin)
  POST   /teams/{id}/run            — çalıştır (background, 202)
  GET    /teams/{id}/runs           — run listesi
  GET    /team-runs/{run_id}        — run detayı + mesaj timeline'ı
"""
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import TenantContext, require_role
from app.core.database import AsyncSessionLocal, get_db
from app.core.redis import get_redis
from app.core.responses import AppError, NotFoundError, success
from app.models.agent import Agent
from app.models.team import Team, TeamMember, TeamRun, TeamRunMessage
from app.schemas.teams import (
    CreateTeamRequest,
    RunTeamRequest,
    TeamResponse,
    TeamRunDetailResponse,
    TeamRunMessageResponse,
    TeamRunResponse,
    UpdateTeamRequest,
)
from app.services.team.roles import DEFAULT_ROLE_PROMPTS, ROLE_LABELS, TEAM_ROLES
from app.services.team.runner import TeamRunner
from app.services.team.team_stats import compute_team_stats

router = APIRouter()
team_runs_router = APIRouter()


async def _get_team_or_404(team_id: uuid.UUID, org_id, db) -> Team:
    team = (await db.execute(
        select(Team).where(Team.id == team_id, Team.organization_id == org_id)
        .options(selectinload(Team.members).selectinload(TeamMember.agent))
    )).scalar_one_or_none()
    if team is None:
        raise NotFoundError("TEAM_NOT_FOUND", "Team not found.")
    return team


async def _validate_member_agents(members, org_id, db) -> None:
    ids = {m.agent_id for m in members}
    rows = (await db.execute(
        select(Agent.id).where(Agent.id.in_(ids), Agent.organization_id == org_id)
    )).scalars().all()
    missing = ids - set(rows)
    if missing:
        raise AppError("AGENT_NOT_FOUND", f"Agent(s) not found in org: {missing}", 422)


@router.get("/roles")
async def list_roles(ctx: TenantContext = Depends(require_role("member"))):
    """Rol kataloğu — `/{team_id}` route'undan ÖNCE tanımlı olmalı."""
    return success([
        {"role": r, "label": ROLE_LABELS.get(r, r), "default_prompt": DEFAULT_ROLE_PROMPTS.get(r, "")}
        for r in TEAM_ROLES
    ])


@router.post("", status_code=201)
async def create_team(
    body: CreateTeamRequest,
    db=Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    dup = (await db.execute(
        select(Team).where(Team.organization_id == ctx.org_id, Team.name == body.name)
    )).scalar_one_or_none()
    if dup:
        raise AppError("TEAM_NAME_CONFLICT", f"A team named '{body.name}' already exists.", 409)

    await _validate_member_agents(body.members, ctx.org_id, db)

    team = Team(
        id=uuid.uuid4(), organization_id=ctx.org_id, created_by=ctx.user_id,
        name=body.name, description=body.description,
    )
    db.add(team)
    await db.flush()
    for i, m in enumerate(body.members):
        db.add(TeamMember(
            id=uuid.uuid4(), team_id=team.id, agent_id=m.agent_id,
            role=m.role, role_prompt=m.role_prompt or "", position=m.position or i,
        ))
    await db.commit()
    team = await _get_team_or_404(team.id, ctx.org_id, db)
    return success(TeamResponse.from_orm(team).model_dump())


@router.get("")
async def list_teams(db=Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    rows = (await db.execute(
        select(Team).where(Team.organization_id == ctx.org_id)
        .options(selectinload(Team.members).selectinload(TeamMember.agent))
        .order_by(Team.created_at.desc())
    )).scalars().all()
    return success([TeamResponse.from_orm(t).model_dump() for t in rows])


@router.get("/{team_id}")
async def get_team(team_id: uuid.UUID, db=Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    team = await _get_team_or_404(team_id, ctx.org_id, db)
    return success(TeamResponse.from_orm(team).model_dump())


@router.patch("/{team_id}")
async def update_team(
    team_id: uuid.UUID,
    body: UpdateTeamRequest,
    db=Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    team = await _get_team_or_404(team_id, ctx.org_id, db)
    if body.name is not None:
        team.name = body.name
    if body.description is not None:
        team.description = body.description
    if body.members is not None:
        await _validate_member_agents(body.members, ctx.org_id, db)
        for old in list(team.members):
            await db.delete(old)
        await db.flush()
        for i, m in enumerate(body.members):
            db.add(TeamMember(
                id=uuid.uuid4(), team_id=team.id, agent_id=m.agent_id,
                role=m.role, role_prompt=m.role_prompt or "", position=m.position or i,
            ))
    team.updated_at = datetime.now(UTC)
    await db.commit()
    team = await _get_team_or_404(team_id, ctx.org_id, db)
    return success(TeamResponse.from_orm(team).model_dump())


@router.delete("/{team_id}", status_code=204)
async def delete_team(team_id: uuid.UUID, db=Depends(get_db), ctx: TenantContext = Depends(require_role("admin"))):
    team = await _get_team_or_404(team_id, ctx.org_id, db)
    await db.delete(team)
    await db.commit()


@router.post("/{team_id}/run", status_code=202)
async def run_team(
    team_id: uuid.UUID,
    body: RunTeamRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("member")),
):
    await _get_team_or_404(team_id, ctx.org_id, db)
    run = TeamRun(
        id=uuid.uuid4(), team_id=team_id, organization_id=ctx.org_id,
        status="pending", input=body.input, created_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    runner = TeamRunner(run_id=run.id, db_factory=AsyncSessionLocal, redis=redis)
    background_tasks.add_task(runner.run)
    return success(TeamRunResponse.from_orm(run).model_dump())


@router.get("/{team_id}/runs")
async def list_team_runs(team_id: uuid.UUID, db=Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    await _get_team_or_404(team_id, ctx.org_id, db)
    rows = (await db.execute(
        select(TeamRun).where(TeamRun.team_id == team_id, TeamRun.organization_id == ctx.org_id)
        .order_by(TeamRun.created_at.desc()).limit(50)
    )).scalars().all()
    return success([TeamRunResponse.from_orm(r).model_dump() for r in rows])


@router.get("/{team_id}/stats")
async def get_team_stats(team_id: uuid.UUID, db=Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    await _get_team_or_404(team_id, ctx.org_id, db)
    runs = (await db.execute(
        select(TeamRun).where(TeamRun.team_id == team_id, TeamRun.organization_id == ctx.org_id)
    )).scalars().all()
    return success(compute_team_stats(list(runs)))


@team_runs_router.get("/{run_id}")
async def get_team_run(run_id: uuid.UUID, db=Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    run = (await db.execute(
        select(TeamRun).where(TeamRun.id == run_id, TeamRun.organization_id == ctx.org_id)
        .options(selectinload(TeamRun.messages))
    )).scalar_one_or_none()
    if run is None:
        raise NotFoundError("TEAM_RUN_NOT_FOUND", "Team run not found.")
    return success(TeamRunDetailResponse(
        run=TeamRunResponse.from_orm(run),
        messages=[TeamRunMessageResponse.from_orm(m) for m in run.messages],
    ).model_dump())
