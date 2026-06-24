"""
Google Workspace tool'ları — D/#13 (Takvim & Drive)

calendar_list_events / calendar_create_event / drive_search / drive_read_file.
Gmail ile AYNI altyapı: kullanıcının bağladığı Google hesabı (ServiceConnection),
token süresi dolmuşsa otomatik yenilenir. Yeni scope'lar (calendar.events,
drive.readonly) gerektirir → kullanıcı hesabı YENİDEN bağlamalı (bkz. connections).

register_google_tools() lifespan'de çağrılır.
"""
from __future__ import annotations

import httpx

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.connections.store import get_valid_access_token

_CAL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_DRIVE = "https://www.googleapis.com/drive/v3/files"
_NO_CONN = "[google error: no Google connection — Bağlantılar'dan Google hesabını bağla (ve Takvim/Drive izinleri için yeniden bağla)]"


async def _token(ctx: ToolContext) -> str | None:
    if ctx.user_id is None or ctx.db is None:
        return None
    return await get_valid_access_token(ctx.db, ctx.user_id, ctx.org_id, "google")


def _scope_hint(status: int, text: str) -> str:
    if status in (401, 403) and ("insufficient" in text.lower() or "scope" in text.lower() or "PERMISSION" in text):
        return " (yetersiz izin — Bağlantılar'dan Google'ı KOPAR ve yeniden bağla; Takvim/Drive izinlerini onayla)"
    return ""


def register_google_tools() -> None:
    if "calendar_list_events" in ToolRegistry.all_names():
        return

    @ToolRegistry.register(
        "calendar_list_events",
        "List upcoming events from the connected Google Calendar (primary). Returns time + title + location.",
        {"type": "object", "properties": {
            "max_results": {"type": "integer", "description": "Max events (default 10, max 25)."},
        }, "required": []},
    )
    async def calendar_list_events(ctx: ToolContext, max_results: int = 10) -> str:
        token = await _token(ctx)
        if not token:
            return _NO_CONN
        n = max(1, min(int(max_results or 10), 25))
        from datetime import UTC, datetime
        now = datetime.now(UTC).isoformat()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(_CAL, headers={"Authorization": f"Bearer {token}"}, params={
                "timeMin": now, "maxResults": n, "singleEvents": "true", "orderBy": "startTime",
            })
        if r.status_code != 200:
            return f"[calendar error: list failed ({r.status_code}) {r.text[:160]}{_scope_hint(r.status_code, r.text)}]"
        items = r.json().get("items", [])
        if not items:
            return "Yaklaşan etkinlik yok."
        out = []
        for e in items:
            start = e.get("start", {})
            when = start.get("dateTime") or start.get("date") or "?"
            loc = f" @ {e['location']}" if e.get("location") else ""
            out.append(f"- {when} · {e.get('summary', '(başlıksız)')}{loc} (id={e.get('id')})")
        return "\n".join(out)

    @ToolRegistry.register(
        "calendar_create_event",
        "Create an event on the connected Google Calendar (primary). Times must be RFC3339 (e.g. '2026-06-25T14:00:00Z').",
        {"type": "object", "properties": {
            "summary": {"type": "string", "description": "Event title."},
            "start": {"type": "string", "description": "Start time, RFC3339 e.g. '2026-06-25T14:00:00Z'."},
            "end": {"type": "string", "description": "End time, RFC3339 e.g. '2026-06-25T15:00:00Z'."},
            "description": {"type": "string", "description": "Optional details."},
        }, "required": ["summary", "start", "end"]},
    )
    async def calendar_create_event(ctx: ToolContext, summary: str, start: str, end: str, description: str = "") -> str:
        token = await _token(ctx)
        if not token:
            return _NO_CONN
        body = {
            "summary": summary,
            "description": description or None,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(_CAL, headers={"Authorization": f"Bearer {token}"}, json=body)
        if r.status_code not in (200, 201):
            return f"[calendar error: create failed ({r.status_code}) {r.text[:160]}{_scope_hint(r.status_code, r.text)}]"
        e = r.json()
        return f"Etkinlik oluşturuldu: {e.get('summary')} ({start} → {end}) · {e.get('htmlLink', '')}"

    @ToolRegistry.register(
        "drive_search",
        "Search files in the connected Google Drive by name/content. Returns id, name, type, modified time.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search text (matches file name and full text)."},
            "max_results": {"type": "integer", "description": "Max files (default 10, max 25)."},
        }, "required": ["query"]},
    )
    async def drive_search(ctx: ToolContext, query: str, max_results: int = 10) -> str:
        token = await _token(ctx)
        if not token:
            return _NO_CONN
        n = max(1, min(int(max_results or 10), 25))
        safe = query.replace("'", "\\'")
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(_DRIVE, headers={"Authorization": f"Bearer {token}"}, params={
                "q": f"name contains '{safe}' or fullText contains '{safe}'",
                "pageSize": n,
                "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
                "orderBy": "modifiedTime desc",
            })
        if r.status_code != 200:
            return f"[drive error: search failed ({r.status_code}) {r.text[:160]}{_scope_hint(r.status_code, r.text)}]"
        files = r.json().get("files", [])
        if not files:
            return "Eşleşen dosya yok."
        return "\n".join(
            f"- {f['name']} · {f.get('mimeType', '').split('.')[-1]} · {f.get('modifiedTime', '')[:10]} (id={f['id']})"
            for f in files
        )

    @ToolRegistry.register(
        "drive_read_file",
        "Read the text content of a Google Drive file by id (from drive_search). Google Docs are exported as text.",
        {"type": "object", "properties": {
            "file_id": {"type": "string", "description": "Drive file id."},
            "max_chars": {"type": "integer", "description": "Max characters (default 6000)."},
        }, "required": ["file_id"]},
    )
    async def drive_read_file(ctx: ToolContext, file_id: str, max_chars: int = 6000) -> str:
        token = await _token(ctx)
        if not token:
            return _NO_CONN
        hdr = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=25) as client:
            meta = await client.get(f"{_DRIVE}/{file_id}", headers=hdr, params={"fields": "name,mimeType"})
            if meta.status_code != 200:
                return f"[drive error: meta failed ({meta.status_code}) {meta.text[:160]}{_scope_hint(meta.status_code, meta.text)}]"
            md = meta.json()
            mime = md.get("mimeType", "")
            name = md.get("name", file_id)
            # Google-native (Docs/Sheets/Slides) → düz metin export; diğerleri → ham indir
            if mime.startswith("application/vnd.google-apps"):
                r = await client.get(f"{_DRIVE}/{file_id}/export", headers=hdr, params={"mimeType": "text/plain"})
            else:
                r = await client.get(f"{_DRIVE}/{file_id}", headers=hdr, params={"alt": "media"})
        if r.status_code != 200:
            return f"[drive error: read failed ({r.status_code}) {r.text[:160]}]"
        text = r.text
        return f"# {name}\n\n{text[:max(500, int(max_chars or 6000))]}"
