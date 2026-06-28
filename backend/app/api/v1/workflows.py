"""
Workflows Router

  POST   /workflows                    — oluştur
  GET    /workflows                    — listele
  GET    /workflows/{id}               — detay
  PATCH  /workflows/{id}               — güncelle
  DELETE /workflows/{id}               — sil
  POST   /workflows/{id}/runs          — çalıştır (Test Et)
  GET    /workflows/{id}/runs          — run geçmişi
  GET    /workflow-runs/{run_id}        — run detayı + node sonuçları
  PATCH  /workflow-runs/{run_id}/cancel — iptal et
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_tenant_context
from app.core.database import get_db
from app.core.responses import AppError, NotFoundError, success
from app.models.workflow import Workflow, WorkflowNodeResult, WorkflowRun
from app.schemas.workflows import CreateWorkflowRequest, UpdateWorkflowRequest, WorkflowResponse

router = APIRouter()
workflow_runs_router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────

def _to_resp(w: Workflow) -> dict:
    return WorkflowResponse(
        id=w.id,
        name=w.name,
        status=w.status,
        graph_json=w.graph_json,
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
    ).model_dump()


def _run_to_resp(r: WorkflowRun) -> dict:
    return {
        "id": str(r.id),
        "workflow_id": str(r.workflow_id),
        "status": r.status,
        "trigger_kind": r.trigger_kind,
        "error": r.error,
        "started_at": r.started_at.isoformat(),
        "ended_at": r.ended_at.isoformat() if r.ended_at else None,
    }


def _nr_to_resp(nr: WorkflowNodeResult) -> dict:
    return {
        "id": str(nr.id),
        "node_id": nr.node_id,
        "status": nr.status,
        "input": nr.input,
        "output": nr.output,
        "error": nr.error,
        "started_at": nr.started_at.isoformat() if nr.started_at else None,
        "ended_at": nr.ended_at.isoformat() if nr.ended_at else None,
    }


async def _get_or_404(wf_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Workflow:
    row = (await db.execute(
        select(Workflow).where(Workflow.id == wf_id, Workflow.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("WORKFLOW_NOT_FOUND", "Workflow bulunamadı.")
    return row


async def _get_run_or_404(run_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> WorkflowRun:
    row = (await db.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("RUN_NOT_FOUND", "Workflow run bulunamadı.")
    return row


# ── Workflow CRUD ─────────────────────────────────────────────

@router.post("")
async def create_workflow(
    body: CreateWorkflowRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    wf = Workflow(id=uuid.uuid4(), organization_id=ctx.org_id, name=body.name, graph_json=body.graph_json)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return success(_to_resp(wf))


@router.get("")
async def list_workflows(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Workflow).where(Workflow.organization_id == ctx.org_id).order_by(Workflow.created_at.desc())
    )).scalars().all()

    # Batch-fetch latest run per workflow (single query)
    if rows:
        wf_ids = [w.id for w in rows]
        latest_subq = (
            select(WorkflowRun.workflow_id, func.max(WorkflowRun.started_at).label("max_started"))
            .where(WorkflowRun.workflow_id.in_(wf_ids))
            .group_by(WorkflowRun.workflow_id)
            .subquery()
        )
        latest_runs_rows = (await db.execute(
            select(WorkflowRun).join(
                latest_subq,
                (WorkflowRun.workflow_id == latest_subq.c.workflow_id)
                & (WorkflowRun.started_at == latest_subq.c.max_started),
            )
        )).scalars().all()
        run_map: dict[uuid.UUID, WorkflowRun] = {r.workflow_id: r for r in latest_runs_rows}
    else:
        run_map = {}

    def _with_last_run(w: Workflow) -> dict:
        d = _to_resp(w)
        run = run_map.get(w.id)
        d["last_run"] = (
            {"status": run.status, "started_at": run.started_at.isoformat(), "trigger_kind": run.trigger_kind}
            if run else None
        )
        return d

    return success([_with_last_run(w) for w in rows])


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_or_404(workflow_id, ctx.org_id, db)
    return success(_to_resp(wf))


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: uuid.UUID,
    body: UpdateWorkflowRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_or_404(workflow_id, ctx.org_id, db)
    if body.name is not None:
        wf.name = body.name
    if body.status is not None:
        wf.status = body.status
    if body.graph_json is not None:
        wf.graph_json = body.graph_json
    await db.commit()
    await db.refresh(wf)
    return success(_to_resp(wf))


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_or_404(workflow_id, ctx.org_id, db)
    await db.delete(wf)
    await db.commit()
    return success({"deleted": True})


# ── Run endpoints ─────────────────────────────────────────────

@router.post("/{workflow_id}/runs")
async def start_run(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_or_404(workflow_id, ctx.org_id, db)
    if wf.status == "unavailable":
        raise AppError("WORKFLOW_UNAVAILABLE", "Bu workflow devre dışı.", status_code=400)

    run = WorkflowRun(
        id=uuid.uuid4(),
        workflow_id=wf.id,
        organization_id=ctx.org_id,
        status="running",
        trigger_kind="manual",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Fire-and-forget
    from app.services.workflow.runner import start_workflow_run
    start_workflow_run(wf.id, run.id, ctx.org_id)

    return success(_run_to_resp(run))


@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(workflow_id, ctx.org_id, db)
    rows = (await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id, WorkflowRun.organization_id == ctx.org_id)
        .order_by(WorkflowRun.started_at.desc())
        .limit(50)
    )).scalars().all()
    return success([_run_to_resp(r) for r in rows])


# ── workflow-runs/* (separate router) ────────────────────────

@workflow_runs_router.get("/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    run = await _get_run_or_404(run_id, ctx.org_id, db)
    node_results = (await db.execute(
        select(WorkflowNodeResult)
        .where(WorkflowNodeResult.run_id == run_id)
        .order_by(WorkflowNodeResult.started_at)
    )).scalars().all()
    return success({
        **_run_to_resp(run),
        "node_results": [_nr_to_resp(nr) for nr in node_results],
    })


@workflow_runs_router.patch("/{run_id}/cancel")
async def cancel_run(
    run_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    run = await _get_run_or_404(run_id, ctx.org_id, db)
    if run.status != "running":
        raise AppError("NOT_RUNNING", "Run zaten çalışmıyor.", status_code=400)
    run.status = "cancelled"
    run.ended_at = datetime.now(UTC)
    await db.commit()
    return success({"cancelled": True})
