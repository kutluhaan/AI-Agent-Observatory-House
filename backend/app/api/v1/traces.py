"""
Traces Router — M8

  GET /traces            — org'un trace listesi (filtreli)   (member)
  GET /traces/{trace_id} — tek trace + event timeline'ı      (member)

Tüm sorgular org-scoped — kullanıcı sadece aktif org'unun trace'lerini görür.
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.deps import TenantContext, require_role
from app.core import clickhouse
from app.core.responses import AppError, NotFoundError, success

logger = structlog.get_logger()
router = APIRouter()


@router.get("")
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    ctx: TenantContext = Depends(require_role("member")),
):
    try:
        traces = await clickhouse.query_traces(ctx.org_id, limit=limit, status=status)
    except Exception as exc:
        logger.error("traces.list_failed", error=str(exc))
        raise AppError("TRACE_STORE_UNAVAILABLE", "Trace store is unavailable.", 503)

    return success(traces)


@router.get("/{trace_id}")
async def get_trace_detail(
    trace_id: uuid.UUID,
    ctx: TenantContext = Depends(require_role("member")),
):
    try:
        trace = await clickhouse.get_trace(ctx.org_id, trace_id)
    except Exception as exc:
        logger.error("traces.get_failed", error=str(exc))
        raise AppError("TRACE_STORE_UNAVAILABLE", "Trace store is unavailable.", 503)

    if trace is None:
        raise NotFoundError("TRACE_NOT_FOUND", "Trace not found.")

    return success(trace)
