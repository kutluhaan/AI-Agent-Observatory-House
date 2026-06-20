"""
HITL Router — M10

  GET    /hitl/{request_id}          — istek durumunu sorgula (member)
  POST   /hitl/{request_id}/approve  — onayla, tool çalışmaya devam eder (member)
  POST   /hitl/{request_id}/reject   — reddet, agent HITLRejectedError alır (member)
  POST   /hitl/{request_id}/modify   — argümanları değiştirerek onayla (member)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import TenantContext, require_role
from app.core.responses import AppError, success
from app.services.hitl import (
    HITLAlreadyResolvedError,
    HITLNotFoundError,
    get_hitl_engine,
)

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────

class HITLRequestResponse(BaseModel):
    request_id: str
    trace_id: str
    org_id: str
    tool_name: str
    tool_arguments: dict[str, Any]
    status: str
    created_at: str
    expires_at: str
    reason: str | None = None
    modified_arguments: dict[str, Any] | None = None
    kind: str = "approval"
    answer: str | None = None


class ModifyBody(BaseModel):
    arguments: dict[str, Any]
    reason: str | None = None


class RejectBody(BaseModel):
    reason: str | None = None


class AnswerBody(BaseModel):
    answer: str


# ─── Helpers ──────────────────────────────────────────────

def _assert_org(hitl_req_org_id: str, ctx_org_id: str) -> None:
    """İsteğin org'u ile token'daki org eşleşmeli."""
    if hitl_req_org_id != str(ctx_org_id):
        raise AppError("HITL_FORBIDDEN", "This HITL request belongs to a different organization.", 403)


# ─── Endpoints ────────────────────────────────────────────

@router.get("/{request_id}")
async def get_hitl_request(
    request_id: str,
    ctx: TenantContext = Depends(require_role("member")),
):
    """HITL isteğinin mevcut durumunu döner."""
    hitl = get_hitl_engine()
    req = await hitl.get(request_id)
    if req is None:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    _assert_org(req.org_id, str(ctx.org_id))
    return success(HITLRequestResponse(**req.__dict__).model_dump())


@router.post("/{request_id}/approve")
async def approve_hitl(
    request_id: str,
    ctx: TenantContext = Depends(require_role("member")),
):
    """Tool çağrısını orijinal argümanlarla onaylar."""
    hitl = get_hitl_engine()
    # Org kontrolü resolve'dan ÖNCE — resolve() runner'ı uyandırır; 403 sonradan gelemez.
    existing = await hitl.get(request_id)
    if existing is None:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    _assert_org(existing.org_id, str(ctx.org_id))
    try:
        req = await hitl.resolve(request_id, "approved")
    except HITLNotFoundError:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    except HITLAlreadyResolvedError as exc:
        raise AppError("HITL_ALREADY_RESOLVED", str(exc), 409)
    return success(HITLRequestResponse(**req.__dict__).model_dump())


@router.post("/{request_id}/reject")
async def reject_hitl(
    request_id: str,
    body: RejectBody = RejectBody(),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Tool çağrısını reddeder; agent HITLRejectedError alır ve durur."""
    hitl = get_hitl_engine()
    existing = await hitl.get(request_id)
    if existing is None:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    _assert_org(existing.org_id, str(ctx.org_id))
    try:
        req = await hitl.resolve(request_id, "rejected", reason=body.reason)
    except HITLNotFoundError:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    except HITLAlreadyResolvedError as exc:
        raise AppError("HITL_ALREADY_RESOLVED", str(exc), 409)
    return success(HITLRequestResponse(**req.__dict__).model_dump())


@router.post("/{request_id}/modify")
async def modify_hitl(
    request_id: str,
    body: ModifyBody,
    ctx: TenantContext = Depends(require_role("member")),
):
    """Tool argümanlarını değiştirerek onaylar; agent modified argümanlarla devam eder."""
    hitl = get_hitl_engine()
    existing = await hitl.get(request_id)
    if existing is None:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    _assert_org(existing.org_id, str(ctx.org_id))
    try:
        req = await hitl.resolve(
            request_id,
            "modified",
            modified_arguments=body.arguments,
            reason=body.reason,
        )
    except HITLNotFoundError:
        raise AppError("HITL_NOT_FOUND", f"HITL request '{request_id}' not found or expired.", 404)
    except HITLAlreadyResolvedError as exc:
        raise AppError("HITL_ALREADY_RESOLVED", str(exc), 409)
    return success(HITLRequestResponse(**req.__dict__).model_dump())


@router.post("/{request_id}/answer")
async def answer_hitl(
    request_id: str,
    body: AnswerBody,
    ctx: TenantContext = Depends(require_role("member")),
):
    """ask_user (kind=question) isteğine kullanıcının yanıtını iletir; agent devam eder."""
    hitl = get_hitl_engine()
    existing = await hitl.get(request_id)
    if existing is None:
        raise AppError("HITL_NOT_FOUND", f"Question '{request_id}' not found or expired.", 404)
    _assert_org(existing.org_id, str(ctx.org_id))
    try:
        req = await hitl.submit_answer(request_id, body.answer)
    except HITLNotFoundError:
        raise AppError("HITL_NOT_FOUND", f"Question '{request_id}' not found or expired.", 404)
    except HITLAlreadyResolvedError as exc:
        raise AppError("HITL_ALREADY_RESOLVED", str(exc), 409)
    return success(HITLRequestResponse(**req.__dict__).model_dump())
