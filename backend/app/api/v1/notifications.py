"""
Notifications Feed Router — D

Agent'ların gönderdiği bildirimler (sent) + sistem olayları (system).

  GET  /notifications               — son N bildirim (member)
  GET  /notifications/unread-count  — okunmamış sayısı (navbar badge) (member)
  POST /notifications/read-all      — hepsini okundu işaretle (member)
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.core.database import get_db
from app.core.responses import success
from app.models.notification_feed import Notification

router = APIRouter()


def _dict(n: Any) -> dict:
    return {"id": str(n.id), "kind": n.kind, "level": n.level, "title": n.title,
            "body": n.body, "source": n.source, "is_read": n.is_read, "created_at": n.created_at.isoformat()}


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    n = (await db.execute(select(func.count()).select_from(Notification).where(
        Notification.organization_id == ctx.org_id, Notification.is_read.is_(False)))).scalar() or 0
    return success({"count": int(n)})


@router.get("")
async def list_notifications(limit: int = Query(default=50, ge=1, le=200),
                             db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    rows = (await db.execute(select(Notification).where(Notification.organization_id == ctx.org_id)
                             .order_by(Notification.created_at.desc()).limit(limit))).scalars().all()
    return success([_dict(n) for n in rows])


@router.post("/read-all")
async def read_all(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require_role("member"))):
    await db.execute(update(Notification).where(
        Notification.organization_id == ctx.org_id, Notification.is_read.is_(False)).values(is_read=True))
    await db.commit()
    return success({"ok": True})
