"""
Bildirim akışı log'u — D

log_notification: feed'e bir girdi yazar (sent: agent send_notification ile gönderdi;
system: ekip run bitti/hata, test bitti). Verilen db session üzerinde commit eder.
Navbar badge'i frontend periyodik poll ile yeniler (ek WS şart değil).
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.models.notification_feed import Notification

logger = structlog.get_logger()


async def log_notification(
    db: Any,
    org_id: uuid.UUID,
    *,
    kind: str,                 # "sent" | "system"
    title: str,
    level: str = "info",       # info | success | error
    body: str = "",
    source: str | None = None,
) -> None:
    """Feed'e girdi ekler (best-effort — hata akışı bozmaz)."""
    try:
        db.add(Notification(
            id=uuid.uuid4(), organization_id=org_id, kind=kind, level=level,
            title=title[:300], body=body or "", source=source,
        ))
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification.log_failed", error=str(exc))
