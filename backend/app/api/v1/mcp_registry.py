"""
MCP Registry Router — D/#2

Resmi MCP Registry'de (registry.modelcontextprotocol.io) mevcut sunucuları arar.
Kullanıcı buradan bir sunucu seçip mevcut `POST /mcp-servers` ile org'una ekler.

  GET /mcp-registry/search?q=&limit=  — registry'de ara (member)
"""
from fastapi import APIRouter, Depends

from app.api.deps import TenantContext, require_role
from app.core.responses import AppError, success
from app.services.mcp.registry import search_registry

router = APIRouter()


@router.get("/search")
async def search_mcp_registry(
    q: str = "",
    limit: int = 20,
    ctx: TenantContext = Depends(require_role("member")),
):
    try:
        results = await search_registry(q, limit)
    except Exception as exc:  # noqa: BLE001
        raise AppError("MCP_REGISTRY_UNREACHABLE", f"MCP registry unreachable: {exc}", 502)
    return success(results)
