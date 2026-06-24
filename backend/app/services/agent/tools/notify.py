"""
Bildirim tool'u — Mesajlaşma kategorisi (loop it.4)

send_notification: org'da yapılandırılmış bir bildirim kanalına (generic webhook)
mesaj gönderir. URL şifreli saklanır (NotificationChannel); tool ada göre bulur,
çözer ve JSON POST eder. Slack/Discord/Teams incoming webhook'larıyla uyumlu olsun
diye gövdede hem `text` (Slack) hem `content` (Discord) gönderilir.

register_notify_tools() lifespan'de çağrılır.
"""
from __future__ import annotations

import httpx
from sqlalchemy import select

from app.core.encryption import decrypt_value
from app.models.notification import NotificationChannel
from app.services.agent.registry import ToolContext, ToolRegistry


async def _resolve_channel(ctx: ToolContext, channel: str | None) -> NotificationChannel | None:
    q = select(NotificationChannel).where(
        NotificationChannel.organization_id == ctx.org_id,
        NotificationChannel.is_active.is_(True),
    )
    if channel:
        q = q.where(NotificationChannel.name == channel)
    else:
        q = q.order_by(NotificationChannel.created_at.asc())
    return (await ctx.db.execute(q)).scalars().first()


async def send_webhook(url: str, text: str) -> tuple[bool, str]:
    """Generic webhook'a JSON POST. (başarı, mesaj) döner. Exception fırlatmaz."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"text": text, "content": text})
        if r.status_code in (200, 201, 202, 204):
            return True, "ok"
        return False, f"{r.status_code} {r.text[:160]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def register_notify_tools() -> None:
    if "send_notification" in ToolRegistry.all_names():
        return

    @ToolRegistry.register(
        "send_notification",
        "Send a notification/message to a pre-configured channel (Slack/Discord/Teams webhook). "
        "Configure channels under 'Bildirim Kanalları'. If 'channel' is omitted, the default channel is used.",
        {"type": "object", "properties": {
            "message": {"type": "string", "description": "The message text to send."},
            "channel": {"type": "string", "description": "Channel name (optional; default channel if omitted)."},
        }, "required": ["message"]},
    )
    async def send_notification(ctx: ToolContext, message: str, channel: str | None = None) -> str:
        if ctx.db is None:
            return "[notify error: no db context]"
        ch = await _resolve_channel(ctx, channel)
        if ch is None:
            hint = f"'{channel}'" if channel else "(default)"
            return f"[notify error: no notification channel {hint} — Bildirim Kanalları'ndan ekle]"
        ok, detail = await send_webhook(decrypt_value(ch.encrypted_url), message)
        # D: feed'e 'sent' girdisi
        from app.services.notifications.log import log_notification
        await log_notification(ctx.db, ctx.org_id, kind="sent", level="success" if ok else "error",
                               title=f"Bildirim → {ch.name}", body=message, source=ch.name)
        return f"Bildirim gönderildi → {ch.name}." if ok else f"[notify error: {ch.name} failed — {detail}]"
