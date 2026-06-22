"""
Agent MCP tool çözümleyici — F7.2

agent.mcp_tools = [{server_id, tool_name, description?, input_schema?}]
→ runner'a verilecek [{name, description, input_schema, url, api_key}] listesi.

Şema config sırasında (discovery'den) saklandığı için burada ağ çağrısı yapılmaz;
yalnızca server URL + (şifre çözülmüş) key eklenir. Yürütme anında bağlanılır.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.models.mcp import McpServer


async def resolve_agent_mcp_tools(db: AsyncSession, agent: Any) -> list[dict]:
    entries = getattr(agent, "mcp_tools", None) or []
    if not entries:
        return []

    # İlgili sunucuları tek seferde yükle
    server_ids = {uuid.UUID(str(e["server_id"])) for e in entries if e.get("server_id")}
    if not server_ids:
        return []
    rows = (await db.execute(
        select(McpServer).where(
            McpServer.id.in_(server_ids),
            McpServer.organization_id == agent.organization_id,
            McpServer.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    servers = {s.id: s for s in rows}

    resolved: list[dict] = []
    for e in entries:
        sid = e.get("server_id")
        if not sid:
            continue
        server = servers.get(uuid.UUID(str(sid)))
        if server is None:
            continue  # sunucu silinmiş/pasif → tool atlanır
        resolved.append({
            "name": e["tool_name"],
            "description": e.get("description") or "",
            "input_schema": e.get("input_schema") or {"type": "object", "properties": {}},
            "url": server.url,
            "api_key": decrypt_value(server.encrypted_api_key) if server.encrypted_api_key else None,
        })
    return resolved
