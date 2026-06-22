"""
MCP (Model Context Protocol) istemcisi — F7.2

Resmi `mcp` SDK + Streamable HTTP transport. "Çağrı başına bağlan" stratejisi:
her işlemde taze bir session açılır, iş biter, kapatılır (stateless, basit).

Uzak MCP sunucularındaki tool'ları keşfetmek (list) ve çağırmak (call) için.
"""
from __future__ import annotations

from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _headers(api_key: str | None) -> dict[str, str] | None:
    return {"Authorization": f"Bearer {api_key}"} if api_key else None


def _content_to_text(result: Any) -> str:
    """CallToolResult.content (TextContent vb. listesi) → düz metin."""
    parts: list[str] = []
    for item in (getattr(result, "content", None) or []):
        text = getattr(item, "text", None)
        parts.append(text if text is not None else str(item))
    return "\n".join(parts) if parts else ""


async def list_mcp_tools(url: str, api_key: str | None = None) -> list[dict]:
    """MCP sunucusunun sunduğu tool'ları döner: [{name, description, input_schema}]."""
    async with streamable_http_client(url, headers=_headers(api_key)) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema or {"type": "object", "properties": {}},
                }
                for t in result.tools
            ]


async def call_mcp_tool(
    url: str,
    api_key: str | None,
    name: str,
    arguments: dict | None,
) -> str:
    """MCP tool'unu çağırır ve sonucu metin olarak döner."""
    async with streamable_http_client(url, headers=_headers(api_key)) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments or {})
            text = _content_to_text(result)
            if getattr(result, "isError", False):
                return f"[mcp error: {text}]"
            return text
