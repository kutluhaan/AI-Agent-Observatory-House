"""
Gmail tool'ları — G1

gmail_search / gmail_read / gmail_send. Kullanıcının bağladığı Gmail hesabını
(ServiceConnection) kullanır; token süresi dolmuşsa otomatik yenilenir.
Bağlantı yoksa zarif hata döner. register_gmail_tools() lifespan'de çağrılır.
"""
from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

import httpx

from app.services.agent.registry import ToolContext, ToolRegistry
from app.services.connections.store import get_valid_access_token

_API = "https://gmail.googleapis.com/gmail/v1/users/me"


async def _token(ctx: ToolContext) -> str | None:
    if ctx.user_id is None or ctx.db is None:
        return None
    return await get_valid_access_token(ctx.db, ctx.user_id, ctx.org_id, "google")


def _header(headers: list[dict], name: str) -> str:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_body(body: dict) -> str:
    d = (body or {}).get("data")
    return base64.urlsafe_b64decode(d).decode("utf-8", "replace") if d else ""


def _find_mime(payload: dict, target: str) -> str:
    if payload.get("mimeType") == target and payload.get("body", {}).get("data"):
        return _decode_body(payload["body"])
    for part in payload.get("parts", []) or []:
        r = _find_mime(part, target)
        if r:
            return r
    return ""


def _extract_text(payload: dict) -> str:
    """Mesaj gövdesinden metin çıkarır: önce text/plain, sonra text/html, sonra kök gövde."""
    if not payload:
        return ""
    return _find_mime(payload, "text/plain") or _find_mime(payload, "text/html") or _decode_body(payload.get("body", {}))


def register_gmail_tools() -> None:
    if "gmail_search" in ToolRegistry.all_names():
        return

    @ToolRegistry.register(
        "gmail_search",
        "Search the connected Gmail inbox. Returns matching messages (id, from, subject, snippet). "
        "Use Gmail query syntax (e.g. 'from:boss is:unread newer_than:7d').",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query."},
                "max_results": {"type": "integer", "description": "Max messages (default 5, max 20)."},
            },
            "required": ["query"],
        },
    )
    async def gmail_search(ctx: ToolContext, query: str, max_results: int = 5) -> str:
        token = await _token(ctx)
        if not token:
            return "[gmail error: no Google connection — connect Gmail under Bağlantılar first]"
        n = max(1, min(int(max_results or 5), 20))
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{_API}/messages", headers={"Authorization": f"Bearer {token}"},
                                 params={"q": query, "maxResults": n})
            if r.status_code != 200:
                return f"[gmail error: search failed ({r.status_code}) {r.text[:160]}]"
            ids = [m["id"] for m in r.json().get("messages", [])]
            if not ids:
                return "No messages matched."
            out = []
            for mid in ids:
                mr = await client.get(f"{_API}/messages/{mid}", headers={"Authorization": f"Bearer {token}"},
                                      params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
                if mr.status_code != 200:
                    continue
                data = mr.json()
                h = data.get("payload", {}).get("headers", [])
                out.append(
                    f"- id={mid} | from: {_header(h,'From')} | subject: {_header(h,'Subject')} "
                    f"| {_header(h,'Date')}\n  {data.get('snippet','')}"
                )
            return "\n".join(out) if out else "No messages matched."

    @ToolRegistry.register(
        "gmail_read",
        "Read a single Gmail message by its id (from gmail_search). Returns headers + body text.",
        {
            "type": "object",
            "properties": {"message_id": {"type": "string", "description": "Gmail message id."}},
            "required": ["message_id"],
        },
    )
    async def gmail_read(ctx: ToolContext, message_id: str) -> str:
        token = await _token(ctx)
        if not token:
            return "[gmail error: no Google connection — connect Gmail under Bağlantılar first]"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{_API}/messages/{message_id}", headers={"Authorization": f"Bearer {token}"},
                                 params={"format": "full"})
            if r.status_code != 200:
                return f"[gmail error: read failed ({r.status_code}) {r.text[:160]}]"
            data = r.json()
            payload = data.get("payload", {})
            h = payload.get("headers", [])
            body = _extract_text(payload).strip()
            return (
                f"From: {_header(h,'From')}\nTo: {_header(h,'To')}\nSubject: {_header(h,'Subject')}\n"
                f"Date: {_header(h,'Date')}\n\n{body[:6000]}"
            )

    @ToolRegistry.register(
        "gmail_send",
        "Send an email from the connected Gmail account.",
        {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject."},
                "body": {"type": "string", "description": "Plain-text email body."},
            },
            "required": ["to", "subject", "body"],
        },
    )
    async def gmail_send(ctx: ToolContext, to: str, subject: str, body: str) -> str:
        token = await _token(ctx)
        if not token:
            return "[gmail error: no Google connection — connect Gmail under Bağlantılar first]"
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{_API}/messages/send", headers={"Authorization": f"Bearer {token}"},
                                  json={"raw": raw})
            if r.status_code not in (200, 202):
                return f"[gmail error: send failed ({r.status_code}) {r.text[:160]}]"
            return f"Email sent to {to} (subject: {subject})."
