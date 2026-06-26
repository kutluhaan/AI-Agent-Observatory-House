"""
Resmi MCP Registry istemcisi — D/#2

Açık katalog (registry.modelcontextprotocol.io) üzerinden mevcut MCP sunucularını arar.
Biz yalnız **Streamable HTTP remote**'u olan sunucuları çalıştırabildiğimiz için,
sonuçları o eksende işaretleriz (addable). Registry yalnız metadata barındırır;
kod/binary değil — bu yüzden sadece keşif + "uzak remote ekleme" yaparız.

Ref: https://registry.modelcontextprotocol.io/  (API v0, OpenAPI dondurulmuş)
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

REGISTRY_BASE = "https://registry.modelcontextprotocol.io"

# Registry popülerlik metriği yayınlamadığı için bilinen yaygın sunucular için
# curated bir sıralama (düşük = daha popüler/önce). İsim namespace'inde aranır.
POPULAR_RANK: dict[str, int] = {
    "github": 0, "slack": 1, "notion": 2, "linear": 3, "sentry": 4, "stripe": 5,
    "postgres": 6, "filesystem": 7, "google": 8, "gmail": 8, "drive": 8, "brave": 9,
    "playwright": 10, "puppeteer": 10, "figma": 11, "atlassian": 12, "jira": 12,
    "cloudflare": 13, "supabase": 14, "fetch": 15, "memory": 16,
    "sequentialthinking": 17, "everything": 18, "time": 19, "sqlite": 20,
}


def _popularity(name: str) -> int:
    n = (name or "").lower()
    for kw, rank in POPULAR_RANK.items():
        if kw in n:
            return rank
    return 999


def _icon_for(s: dict, http_remote: dict | None) -> str | None:
    """İkonu türet: GitHub repo → org avatarı; yoksa remote/repo domain favicon'u."""
    repo = (s.get("repository") or {}).get("url") or ""
    m = re.match(r"https?://github\.com/([^/]+)", repo)
    if m:
        return f"https://github.com/{m.group(1)}.png?size=64"
    url = (http_remote or {}).get("url") or repo
    if url:
        host = urlparse(url).hostname
        if host:
            return f"https://www.google.com/s2/favicons?domain={host}&sz=64"
    return None


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
    name = s.get("name", "")
    return {
        "name": name,
        "description": s.get("description", "") or "",
        "version": s.get("version"),
        "repository_url": (s.get("repository") or {}).get("url"),
        "remote_url": (http_remote or {}).get("url"),
        "addable": http_remote is not None,   # sadece HTTP remote'u olanları ekleyebiliriz
        "requires_auth": requires_auth,        # ekledikten sonra API anahtarı gerekebilir
        "icon_url": _icon_for(s, http_remote),
        "popularity": _popularity(name),
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
    results = [_simplify(e) for e in data.get("servers", [])]
    # Eklenebilir (HTTP remote) olanlar önce, sonra popülerliğe göre, sonra isim
    results.sort(key=lambda r: (not r["addable"], r["popularity"], r["name"].lower()))
    return results
