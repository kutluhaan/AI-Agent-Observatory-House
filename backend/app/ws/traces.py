"""
WebSocket — canlı trace event akışı (M8).

ConnectionManager org bazlı abonelikleri tutar. Consumer her event'i
broadcast(org_id, event) ile iletir; sadece o org'a bağlı soketler alır
(org izolasyonu).

/ws/traces handshake'inde access_token cookie'si doğrulanır ve kullanıcının
aktif org'una abone olunur. Org context'i yoksa bağlantı reddedilir.
"""
import asyncio
import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import get_redis_pool
from app.services.auth_context import resolve_user_from_token

logger = structlog.get_logger()
router = APIRouter()


class ConnectionManager:
    """org_id → aktif WebSocket bağlantıları."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, org_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(org_id, set()).add(ws)

    async def disconnect(self, org_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(org_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._connections.pop(org_id, None)

    def connection_count(self, org_id: str) -> int:
        return len(self._connections.get(org_id, ()))

    async def broadcast(self, org_id: str, event: dict[str, Any]) -> None:
        """Event'i SADECE ilgili org'un soketlerine iletir."""
        conns = list(self._connections.get(org_id, ()))
        if not conns:
            return
        message = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(org_id, ws)


# Uygulama genelinde tek manager — consumer ve endpoint bunu paylaşır
manager = ConnectionManager()


@router.websocket("/traces")
async def trace_stream(websocket: WebSocket) -> None:
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4401)  # unauthorized
        return

    redis = await get_redis_pool()
    user = await resolve_user_from_token(token, redis)
    if user is None or user.org_id is None:
        await websocket.close(code=4403)  # forbidden — org context gerekli
        return

    org_id = str(user.org_id)
    await manager.connect(org_id, websocket)
    try:
        while True:
            # İstemciden mesaj beklemiyoruz; bağlantı açık kaldıkça event iter.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(org_id, websocket)
