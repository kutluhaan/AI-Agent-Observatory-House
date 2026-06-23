"""
Resmi MCP Registry istemcisi — D/#2

Açık katalog (registry.modelcontextprotocol.io) üzerinden mevcut MCP sunucularını arar.
Biz yalnız **Streamable HTTP remote**'u olan sunucuları çalıştırabildiğimiz için,
sonuçları o eksende işaretleriz (addable). Registry yalnız metadata barındırır;
kod/binary değil — bu yüzden sadece keşif + "uzak remote ekleme" yaparız.

Ref: https://registry.modelcontextprotocol.io/  (API v0, OpenAPI dondurulmuş)
"""
from __future__ import annotations

import httpx

REGISTRY_BASE = "https://registry.modelcontextprotocol.io"


def _simplify(entry: dict) -> dict:
    # Registry kaydı: {"server": {...}, "_meta": {...}} ya da düz {...}
    s = entry.get("server", entry) or {}
    remotes = s.get("remotes") or []
    http_remote = next(
        (rm for rm in remotes if (rm.get("type") or rm.get("transport_type")) == "streamable-http"),
        None,
    )
    headers = (http_remote or {}).get("headers") or []
    requires_auth = any(h.get("isRequired") or h.get("isSecret") for h in headers)
    return {
        "name": s.get("name", ""),
        "description": s.get("description", "") or "",
        "version": s.get("version"),
        "repository_url": (s.get("repository") or {}).get("url"),
        "remote_url": (http_remote or {}).get("url"),
        "addable": http_remote is not None,   # sadece HTTP remote'u olanları ekleyebiliriz
        "requires_auth": requires_auth,        # ekledikten sonra API anahtarı gerekebilir
    }


async def search_registry(query: str = "", limit: int = 20) -> list[dict]:
    """Resmi registry'de MCP sunucusu ara; sadeleştirilmiş, eklenebilir-işaretli liste döndür."""
    params: dict = {"limit": min(max(limit, 1), 50)}
    if query.strip():
        params["search"] = query.strip()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{REGISTRY_BASE}/v0/servers", params=params)
        resp.raise_for_status()
        data = resp.json()
    return [_simplify(e) for e in data.get("servers", [])]
