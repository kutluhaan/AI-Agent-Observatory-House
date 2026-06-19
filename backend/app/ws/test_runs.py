"""
WebSocket — test run progress akışı (M11).

Mevcut traces ConnectionManager'ı yeniden kullanır (aynı org-bazlı yayın sistemi).
ExperimentRunner, case tamamlandıkça manager.broadcast(org_id, {...}) çağırır;
bu endpoint'e bağlı istemciler o org'un test run event'lerini alır.

Event tipleri:
  case_completed  — bir case başarıyla bitti (passed/skipped)
  case_failed     — bir case başarısız veya hata aldı
  run_completed   — tüm run bitti, summary mevcut
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import get_redis_pool
from app.services.auth_context import resolve_user_from_token
from app.ws.traces import manager  # traces manager'ını paylaş — aynı org yayın kanalı

router = APIRouter()


@router.websocket("/test-runs")
async def test_run_stream(websocket: WebSocket) -> None:
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
