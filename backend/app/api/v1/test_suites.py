"""
Test Suites Router — M11

  POST   /test-suites               — suite oluştur (admin)
  GET    /test-suites               — listele (member)
  GET    /test-suites/{id}          — detay (member)
  PATCH  /test-suites/{id}          — güncelle (admin)
  DELETE /test-suites/{id}          — sil (admin)
  POST   /test-suites/{id}/run      — çalıştır (member) → background task
  GET    /test-runs/{run_id}        — run detayı + case sonuçları (member)
  GET    /test-suites/{id}/runs     — suite'e ait run geçmişi (member)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import AsyncSessionLocal, get_db
from app.core.redis import get_redis
from app.core.responses import AppError, NotFoundError, success
from app.models.test_suite import TestCase, TestCaseResult, TestRun, TestSuite
from app.schemas.test_suites import (
    CreateTestSuiteRequest,
    RunTestSuiteRequest,
    TestCaseResultResponse,
    TestRunDetailResponse,
    TestRunResponse,
    TestSuiteResponse,
    UpdateTestSuiteRequest,
)
from app.services.test_suite.experiment_runner import ExperimentRunner
from app.services.test_suite.parser import ParseError, parse_yaml
from app.ws.traces import manager as ws_manager

logger = structlog.get_logger()
router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────

async def _get_suite_or_404(
    suite_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> TestSuite:
    result = await db.execute(
        select(TestSuite).where(
            TestSuite.id == suite_id,
            TestSuite.organization_id == org_id,
        )
    )
    suite = result.scalar_one_or_none()
    if suite is None:
        raise NotFoundError("SUITE_NOT_FOUND", "Test suite not found.")
    return suite


async def _get_run_or_404(
    run_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> TestRun:
    result = await db.execute(
        select(TestRun).where(
            TestRun.id == run_id,
            TestRun.organization_id == org_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("RUN_NOT_FOUND", "Test run not found.")
    return run


def _parse_or_error(config_yaml: str) -> None:
    """YAML parse edebiliyorsa OK, aksi halde 422 fırlatır."""
    try:
        parse_yaml(config_yaml)
    except ParseError as exc:
        raise AppError("INVALID_TEST_YAML", str(exc), 422)


# ─── Suite CRUD ───────────────────────────────────────────

@router.post("", status_code=201)
async def create_test_suite(
    body: CreateTestSuiteRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    _parse_or_error(body.config_yaml)

    existing = await db.execute(
        select(TestSuite).where(
            TestSuite.organization_id == ctx.org_id,
            TestSuite.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise AppError("SUITE_NAME_CONFLICT", f"A suite named '{body.name}' already exists.", 409)

    # YAML'dan case'leri parse edip DB'ye yaz
    parsed = parse_yaml(body.config_yaml)
    suite = TestSuite(
        id=uuid.uuid4(),
        organization_id=ctx.org_id,
        created_by=ctx.user_id,
        name=body.name,
        description=body.description,
        config_yaml=body.config_yaml,
    )
    db.add(suite)
    await db.flush()

    for pc in parsed.cases:
        agent_id = pc.agent_id or parsed.agent_id
        tc = TestCase(
            id=uuid.uuid4(),
            suite_id=suite.id,
            agent_id=agent_id,
            name=pc.name,
            input=pc.input,
            assertions=[{"type": a.type, "value": a.value} for a in pc.assertions],
            judges=[j.to_dict() for j in pc.judges],
            repeat=pc.repeat,
            min_pass_rate=pc.min_pass_rate,
            expected_output=pc.expected_output,
            rag_context=pc.rag_context,
        )
        db.add(tc)

    await db.commit()
    await db.refresh(suite)
    return success(TestSuiteResponse.from_orm(suite).model_dump())


@router.get("")
async def list_test_suites(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    result = await db.execute(
        select(TestSuite)
        .where(TestSuite.organization_id == ctx.org_id)
        .order_by(TestSuite.created_at.desc())
    )
    suites = result.scalars().all()
    return success([TestSuiteResponse.from_orm(s).model_dump() for s in suites])


@router.get("/{suite_id}")
async def get_test_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    suite = await _get_suite_or_404(suite_id, ctx.org_id, db)  # type: ignore[arg-type]
    return success(TestSuiteResponse.from_orm(suite).model_dump())


@router.patch("/{suite_id}")
async def update_test_suite(
    suite_id: uuid.UUID,
    body: UpdateTestSuiteRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    suite = await _get_suite_or_404(suite_id, ctx.org_id, db)  # type: ignore[arg-type]

    if body.config_yaml is not None:
        _parse_or_error(body.config_yaml)

    if body.name is not None and body.name != suite.name:
        conflict = await db.execute(
            select(TestSuite).where(
                TestSuite.organization_id == ctx.org_id,
                TestSuite.name == body.name,
                TestSuite.id != suite_id,
            )
        )
        if conflict.scalar_one_or_none():
            raise AppError("SUITE_NAME_CONFLICT", f"A suite named '{body.name}' already exists.", 409)

    update_fields = body.model_dump(exclude_unset=True)
    for field_name, value in update_fields.items():
        setattr(suite, field_name, value)

    # YAML güncellendiyse case'leri yeniden oluştur
    if body.config_yaml is not None:
        # Eski case'leri sil (cascade)
        old_cases = (await db.execute(
            select(TestCase).where(TestCase.suite_id == suite_id)
        )).scalars().all()
        for tc in old_cases:
            await db.delete(tc)

        parsed = parse_yaml(body.config_yaml)
        for pc in parsed.cases:
            agent_id = pc.agent_id or parsed.agent_id
            db.add(TestCase(
                id=uuid.uuid4(),
                suite_id=suite.id,
                agent_id=agent_id,
                name=pc.name,
                input=pc.input,
                assertions=[{"type": a.type, "value": a.value} for a in pc.assertions],
                judges=[j.to_dict() for j in pc.judges],
                repeat=pc.repeat,
                min_pass_rate=pc.min_pass_rate,
                expected_output=pc.expected_output,
                rag_context=pc.rag_context,
            ))

    suite.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(suite)
    return success(TestSuiteResponse.from_orm(suite).model_dump())


@router.delete("/{suite_id}", status_code=204)
async def delete_test_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    suite = await _get_suite_or_404(suite_id, ctx.org_id, db)  # type: ignore[arg-type]
    await db.delete(suite)
    await db.commit()


# ─── Run ──────────────────────────────────────────────────

@router.post("/{suite_id}/run", status_code=202)
async def run_test_suite(
    suite_id: uuid.UUID,
    body: RunTestSuiteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    ctx: TenantContext = Depends(require_role("member")),
):
    """
    Test suite'i başlatır.
    TestRun kaydı oluşturulur ve HTTP 202 ile run_id döner.
    ExperimentRunner arka planda çalışır; WebSocket üzerinden progress izlenebilir.
    """
    suite = await _get_suite_or_404(suite_id, ctx.org_id, db)  # type: ignore[arg-type]

    run = TestRun(
        id=uuid.uuid4(),
        suite_id=suite.id,
        organization_id=ctx.org_id,
        status="pending",
        parallel=body.parallel,
        created_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    experiment = ExperimentRunner(
        run_id=run.id,
        db_factory=AsyncSessionLocal,
        redis=redis,
        ws_manager=ws_manager,
    )
    background_tasks.add_task(experiment.run)

    return success(TestRunResponse.from_orm(run).model_dump())


@router.get("/{suite_id}/runs")
async def list_suite_runs(
    suite_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    await _get_suite_or_404(suite_id, ctx.org_id, db)  # type: ignore[arg-type]
    result = await db.execute(
        select(TestRun)
        .where(
            TestRun.suite_id == suite_id,
            TestRun.organization_id == ctx.org_id,
        )
        .order_by(TestRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return success([TestRunResponse.from_orm(r).model_dump() for r in runs])


# ─── Test Run detail (ayrı prefix /test-runs altında) ─────

test_runs_router = APIRouter()


@test_runs_router.get("/{run_id}")
async def get_test_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    run = await _get_run_or_404(run_id, ctx.org_id, db)  # type: ignore[arg-type]

    result = await db.execute(
        select(TestCaseResult).where(TestCaseResult.run_id == run_id)
    )
    case_results = result.scalars().all()

    return success(
        TestRunDetailResponse(
            run=TestRunResponse.from_orm(run),
            case_results=[TestCaseResultResponse.from_orm(r) for r in case_results],
        ).model_dump()
    )
