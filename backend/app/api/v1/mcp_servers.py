"""
MCP Servers Router — F7.2

Org-bazlı MCP (Model Context Protocol) sunucu kaydı + tool keşfi.

  POST   /mcp-servers              — sunucu ekle (admin)
  GET    /mcp-servers              — listele (member)
  PATCH  /mcp-servers/{id}         — güncelle (admin)
  DELETE /mcp-servers/{id}         — sil (admin)
  GET    /mcp-servers/{id}/tools   — sunucudaki tool'ları keşfet (member)
"""
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.encryption import decrypt_value, encrypt_value
from app.core.responses import AppError, NotFoundError, success
from app.models.mcp import McpServer
from app.schemas.mcp import (
    CreateMcpServerRequest,
    McpServerResponse,
    McpToolInfo,
    UpdateMcpServerRequest,
)
from app.services.mcp.client import list_mcp_tools

router = APIRouter()


async def _get_or_404(server_id: uuid.UUID, org_id, db: AsyncSession) -> McpServer:
    row = (await db.execute(
        select(McpServer).where(McpServer.id == server_id, McpServer.organization_id == org_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("MCP_SERVER_NOT_FOUND", "MCP server not found.")
    return row


@router.post("", status_code=201)
async def create_mcp_server(
    body: CreateMcpServerRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    existing = (await db.execute(
        select(McpServer).where(
            McpServer.organization_id == ctx.org_id, McpServer.name == body.name
        )
    )).scalar_one_or_none()
    if existing:
        raise AppError("MCP_NAME_CONFLICT", f"An MCP server named '{body.name}' already exists.", 409)

    server = McpServer(
        id=uuid.uuid4(),
        organization_id=ctx.org_id,
        name=body.name,
        url=body.url,
        encrypted_api_key=encrypt_value(body.api_key) if body.api_key else None,
        is_active=True,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return success(McpServerResponse.from_orm(server).model_dump())


@router.get("")
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    rows = (await db.execute(
        select(McpServer).where(McpServer.organization_id == ctx.org_id).order_by(McpServer.created_at.desc())
    )).scalars().all()
    return success([McpServerResponse.from_orm(s).model_dump() for s in rows])


@router.patch("/{server_id}")
async def update_mcp_server(
    server_id: uuid.UUID,
    body: UpdateMcpServerRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    server = await _get_or_404(server_id, ctx.org_id, db)
    if body.name is not None:
        server.name = body.name
    if body.url is not None:
        server.url = body.url
    if body.is_active is not None:
        server.is_active = body.is_active
    if body.api_key is not None:
        server.encrypted_api_key = encrypt_value(body.api_key) if body.api_key else None
    server.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(server)
    return success(McpServerResponse.from_orm(server).model_dump())


@router.delete("/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    server = await _get_or_404(server_id, ctx.org_id, db)
    await db.delete(server)
    await db.commit()


@router.get("/{server_id}/tools")
async def discover_mcp_tools(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    """MCP sunucusuna bağlanıp sunduğu tool'ları listeler (canlı keşif)."""
    server = await _get_or_404(server_id, ctx.org_id, db)
    api_key = decrypt_value(server.encrypted_api_key) if server.encrypted_api_key else None
    try:
        tools = await list_mcp_tools(server.url, api_key)
    except Exception as exc:
        raise AppError("MCP_CONNECT_FAILED", f"Could not reach MCP server: {exc}", 502)
    return success([McpToolInfo(**t).model_dump() for t in tools])
