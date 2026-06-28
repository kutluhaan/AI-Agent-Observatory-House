"""
Workflow Integration Node Executor — Faz 4

Her servis için ToolRegistry veya direkt protokol üzerinden çağrı yapar.
Tüm param değerlerinde {{node_id.output}} template desteği vardır.
"""
from __future__ import annotations

import json
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent.registry import ToolContext, ToolRegistry
from app.core.redis import get_redis_pool

_TEMPLATE_RE = re.compile(r'\{\{([\w-]+)\.(output|input)\}\}')


def _resolve(val: str, context: dict[str, dict]) -> str:
    return _TEMPLATE_RE.sub(lambda m: context.get(m.group(1), {}).get(m.group(2), ""), str(val or ""))


def _resolve_params(params: dict, context: dict[str, dict]) -> dict:
    return {k: _resolve(v, context) for k, v in params.items() if v not in (None, "")}


def _coerce(params: dict) -> dict:
    """Auto-convert numeric string values to int/float for tool compatibility."""
    result = {}
    for k, v in params.items():
        if isinstance(v, str):
            if v.isdigit():
                result[k] = int(v)
            else:
                try:
                    result[k] = float(v)
                except ValueError:
                    result[k] = v
        else:
            result[k] = v
    return result


async def _make_ctx(org_id: uuid.UUID, db: AsyncSession, user_id: uuid.UUID | None = None) -> ToolContext:
    redis = await get_redis_pool()
    return ToolContext(
        org_id=org_id,
        trace_id=str(uuid.uuid4()),
        db=db,
        redis=redis,
        user_id=user_id,
    )


async def execute_integration(
    service: str,
    operation: str,
    params: dict,
    context: dict[str, dict],
    org_id: uuid.UUID,
    db: AsyncSession,
) -> str:
    resolved = _coerce(_resolve_params(params or {}, context))

    if service in ("gmail", "gcalendar", "gdrive"):
        return await _google(operation, resolved, org_id, db)
    if service == "github":
        return await _github(operation, resolved, org_id, db)
    if service == "db":
        return await _sql(operation, resolved, org_id, db)
    if service == "mcp":
        return await _mcp(resolved, org_id, db)
    if service == "http":
        return await _http(resolved, org_id, db)

    return f"Bilinmeyen servis: {service}"


# ── Google (Gmail / Calendar / Drive) ─────────────────────────

async def _google(operation: str, params: dict, org_id: uuid.UUID, db: AsyncSession) -> str:
    from app.models.connection import ServiceConnection

    conn = (await db.execute(
        select(ServiceConnection).where(
            ServiceConnection.organization_id == org_id,
            ServiceConnection.provider == "google",
        ).limit(1)
    )).scalar_one_or_none()

    if conn is None:
        return "Google bağlantısı bulunamadı. Bağlantılar sayfasından Google hesabı ekleyin."

    tool = ToolRegistry.get(operation)
    if tool is None:
        return f"Araç bulunamadı: {operation}"

    ctx = await _make_ctx(org_id, db, user_id=conn.user_id)
    try:
        return str(await tool.handler(ctx, **params))
    except Exception as exc:
        return f"Google araç hatası: {exc}"


# ── GitHub ────────────────────────────────────────────────────

async def _github(operation: str, params: dict, org_id: uuid.UUID, db: AsyncSession) -> str:
    tool = ToolRegistry.get(operation)
    if tool is None:
        return f"Araç bulunamadı: {operation}"

    ctx = await _make_ctx(org_id, db)
    try:
        return str(await tool.handler(ctx, **params))
    except Exception as exc:
        return f"GitHub araç hatası: {exc}"


# ── SQL / DB ──────────────────────────────────────────────────

async def _sql(operation: str, params: dict, org_id: uuid.UUID, db: AsyncSession) -> str:
    tool = ToolRegistry.get(operation)
    if tool is None:
        return f"Araç bulunamadı: {operation}"

    ctx = await _make_ctx(org_id, db)
    try:
        return str(await tool.handler(ctx, **params))
    except Exception as exc:
        return f"SQL araç hatası: {exc}"


# ── MCP ──────────────────────────────────────────────────────

async def _mcp(params: dict, org_id: uuid.UUID, db: AsyncSession) -> str:
    server_id_str = params.get("server_id", "")
    tool_name = params.get("tool_name", "")
    tool_params_raw = params.get("tool_params", "")

    if not server_id_str or not tool_name:
        return "MCP: server_id ve tool_name zorunlu."

    try:
        server_id = uuid.UUID(server_id_str)
    except ValueError:
        return f"Geçersiz server_id: {server_id_str}"

    try:
        tool_args = json.loads(tool_params_raw) if tool_params_raw else {}
    except json.JSONDecodeError:
        return f"tool_params geçerli JSON değil: {tool_params_raw}"

    from app.models.mcp import McpServer
    from app.core.encryption import decrypt_value

    server = (await db.execute(
        select(McpServer).where(McpServer.id == server_id, McpServer.organization_id == org_id)
    )).scalar_one_or_none()

    if server is None:
        return "MCP sunucusu bulunamadı."

    api_key = decrypt_value(server.encrypted_api_key) if server.encrypted_api_key else None

    from app.services.mcp.client import call_mcp_tool
    try:
        return await call_mcp_tool(server.url, api_key, tool_name, tool_args)
    except Exception as exc:
        return f"MCP araç hatası: {exc}"


# ── HTTP (CustomTool) ─────────────────────────────────────────

async def _http(params: dict, org_id: uuid.UUID, db: AsyncSession) -> str:
    tool_id_str = params.get("tool_id", "")
    tool_params_raw = params.get("tool_params", "")

    if not tool_id_str:
        return "HTTP: tool_id zorunlu."

    try:
        tool_id = uuid.UUID(tool_id_str)
    except ValueError:
        return f"Geçersiz tool_id: {tool_id_str}"

    try:
        tool_args = json.loads(tool_params_raw) if tool_params_raw else {}
    except json.JSONDecodeError:
        return f"tool_params geçerli JSON değil: {tool_params_raw}"

    from app.models.custom_tool import CustomTool
    from app.core.encryption import decrypt_value
    import httpx

    ct = (await db.execute(
        select(CustomTool).where(CustomTool.id == tool_id, CustomTool.organization_id == org_id)
    )).scalar_one_or_none()

    if ct is None:
        return "Özel HTTP araç bulunamadı."

    headers: dict = {}
    if ct.encrypted_headers:
        try:
            headers = json.loads(decrypt_value(ct.encrypted_headers))
        except Exception:
            pass

    timeout = ct.timeout_seconds or 30
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if ct.method.upper() in ("GET", "DELETE"):
                resp = await client.request(ct.method, ct.url, params=tool_args, headers=headers)
            else:
                resp = await client.request(ct.method, ct.url, json=tool_args, headers=headers)
        return resp.text[:4000]
    except Exception as exc:
        return f"HTTP araç hatası: {exc}"
