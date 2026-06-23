"""
Custom Tools Router — B1 (#1)

Org bazlı, kullanıcı tanımlı HTTP tool CRUD + deneme.
  POST   /custom-tools            — oluştur (admin)
  GET    /custom-tools            — listele (member)
  PATCH  /custom-tools/{id}       — güncelle (admin)
  DELETE /custom-tools/{id}       — sil (admin)
  POST   /custom-tools/{id}/test  — örnek argümanlarla dene (member)
"""
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.encryption import decrypt_value, encrypt_value
from app.core.responses import AppError, NotFoundError, success
from app.models.custom_tool import CustomTool
from app.schemas.custom_tools import (
    CreateCustomToolRequest,
    CustomToolResponse,
    TestCustomToolRequest,
    UpdateCustomToolRequest,
)
from app.services.agent.custom_tools import call_custom_tool

router = APIRouter()


def _header_names(obj: CustomTool) -> list[str]:
    if not obj.encrypted_headers:
        return []
    try:
        return list(json.loads(decrypt_value(obj.encrypted_headers)).keys())
    except Exception:  # noqa: BLE001
        return []


def _headers_dict(obj: CustomTool) -> dict:
    if not obj.encrypted_headers:
        return {}
    try:
        return json.loads(decrypt_value(obj.encrypted_headers))
    except Exception:  # noqa: BLE001
        return {}


async def _get_or_404(tool_id: uuid.UUID, org_id, db: AsyncSession) -> CustomTool:
    row = (await db.execute(
        select(CustomTool).where(CustomTool.id == tool_id, CustomTool.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("CUSTOM_TOOL_NOT_FOUND", "Custom tool not found.")
    return row


@router.post("", status_code=201)
async def create_custom_tool(
    body: CreateCustomToolRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    dup = (await db.execute(
        select(CustomTool).where(CustomTool.organization_id == ctx.org_id, CustomTool.name == body.name)
    )).scalar_one_or_none()
    if dup:
        raise AppError("CUSTOM_TOOL_NAME_CONFLICT", f"A custom tool named '{body.name}' already exists.", 409)

    tool = CustomTool(
        id=uuid.uuid4(), organization_id=ctx.org_id, created_by=ctx.user_id,
        name=body.name, description=body.description, method=body.method, url=body.url,
        encrypted_headers=encrypt_value(json.dumps(body.headers)) if body.headers else None,
        parameters=body.parameters, timeout_seconds=body.timeout_seconds, is_active=True,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return success(CustomToolResponse.from_orm(tool, _header_names(tool)).model_dump())


@router.get("")
async def list_custom_tools(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    rows = (await db.execute(
        select(CustomTool).where(CustomTool.organization_id == ctx.org_id).order_by(CustomTool.created_at.desc())
    )).scalars().all()
    return success([CustomToolResponse.from_orm(t, _header_names(t)).model_dump() for t in rows])


@router.patch("/{tool_id}")
async def update_custom_tool(
    tool_id: uuid.UUID,
    body: UpdateCustomToolRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    tool = await _get_or_404(tool_id, ctx.org_id, db)
    if body.name is not None:
        tool.name = body.name
    if body.description is not None:
        tool.description = body.description
    if body.method is not None:
        tool.method = body.method
    if body.url is not None:
        tool.url = body.url
    if body.parameters is not None:
        tool.parameters = body.parameters
    if body.timeout_seconds is not None:
        tool.timeout_seconds = body.timeout_seconds
    if body.is_active is not None:
        tool.is_active = body.is_active
    if body.headers is not None:
        tool.encrypted_headers = encrypt_value(json.dumps(body.headers)) if body.headers else None
    tool.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(tool)
    return success(CustomToolResponse.from_orm(tool, _header_names(tool)).model_dump())


@router.delete("/{tool_id}", status_code=204)
async def delete_custom_tool(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    tool = await _get_or_404(tool_id, ctx.org_id, db)
    await db.delete(tool)
    await db.commit()


@router.post("/{tool_id}/test")
async def test_custom_tool(
    tool_id: uuid.UUID,
    body: TestCustomToolRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """Tool'u verilen örnek argümanlarla gerçekten çağırır (deneme)."""
    tool = await _get_or_404(tool_id, ctx.org_id, db)
    result = await call_custom_tool(
        method=tool.method, url=tool.url, headers=_headers_dict(tool),
        arguments=body.arguments, timeout=tool.timeout_seconds,
    )
    return success({"result": result})
