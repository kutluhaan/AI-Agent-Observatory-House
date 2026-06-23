"""
WebSocket — ekip run canlı akışı (C2).

Org-bazlı traces manager'ını yeniden kullanır. TeamRunner + team tool'ları yeni
mesaj/durum oldukça manager.broadcast(org_id, {type:"team_run_updated", run_id})
gönderir; bu endpoint'e bağlı istemci ilgili run'ı yeniden çeker.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import get_redis_pool
from app.services.auth_context import resolve_user_from_token
from app.ws.traces import manager

router = APIRouter()


@router.websocket("/team-runs")
async def team_run_stream(websocket: WebSocket) -> None:
    token = websocket.cookies.get("access_token")
    if not token:
        await websocket.close(code=4401)
        return

    redis = await get_redis_pool()
    user = await resolve_user_from_token(token, redis)
    if user is None or user.org_id is None:
        await websocket.close(code=4403)
        return

    org_id = str(user.org_id)
    await manager.connect(org_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(org_id, websocket)
