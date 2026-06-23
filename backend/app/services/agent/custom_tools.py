"""
Kullanıcı tanımlı HTTP tool çalıştırıcı + çözümleyici — B1 (#1)

call_custom_tool: LLM argümanlarını URL placeholder + gövde/sorgu olarak gönderir,
yanıt metnini döner. resolve_agent_custom_tools: agent'ın seçtiği custom tool'ları
(şifreli header çözülmüş) runner'a verilecek biçimde hazırlar.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value
from app.models.custom_tool import CustomTool

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_MAX_RESULT = 4000


async def call_custom_tool(
    *, method: str, url: str, headers: dict | None, arguments: dict | None, timeout: int = 20,
) -> str:
    args = arguments or {}
    used: set[str] = set()

    def _repl(m: re.Match) -> str:
        k = m.group(1)
        used.add(k)
        return str(args.get(k, m.group(0)))

    final_url = _PLACEHOLDER.sub(_repl, url)
    rest = {k: v for k, v in args.items() if k not in used}
    m = (method or "GET").upper()

    req: dict[str, Any] = {"headers": headers or {}}
    if m in ("GET", "DELETE"):
        req["params"] = rest
    else:
        req["json"] = rest

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(m, final_url, **req)
    except Exception as exc:  # noqa: BLE001
        return f"[custom tool error: {exc}]"

    text = r.text
    if len(text) > _MAX_RESULT:
        text = text[:_MAX_RESULT] + "…[truncated]"
    if r.status_code >= 400:
        return f"[custom tool HTTP {r.status_code}] {text}"
    return text or "(empty response)"


async def resolve_agent_custom_tools(db: AsyncSession, agent: Any) -> list[dict]:
    ids = getattr(agent, "custom_tool_ids", None) or []
    if not ids:
        return []
    try:
        uuids = [uuid.UUID(str(i)) for i in ids]
    except (ValueError, TypeError):
        return []
    rows = (await db.execute(
        select(CustomTool).where(
            CustomTool.id.in_(uuids),
            CustomTool.organization_id == agent.organization_id,
            CustomTool.is_active == True,  # noqa: E712
        )
    )).scalars().all()

    out: list[dict] = []
    for t in rows:
        headers: dict = {}
        if t.encrypted_headers:
            try:
                headers = json.loads(decrypt_value(t.encrypted_headers))
            except Exception:  # noqa: BLE001
                headers = {}
        out.append({
            "name": t.name,
            "description": t.description or f"Custom HTTP tool: {t.name}",
            "input_schema": t.parameters or {"type": "object", "properties": {}},
            "method": t.method,
            "url": t.url,
            "headers": headers,
            "timeout": t.timeout_seconds,
        })
    return out
