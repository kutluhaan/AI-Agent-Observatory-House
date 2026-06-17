"""
Trace Consumer — Redis Stream'den okur, ClickHouse'a persist eder, WebSocket'e iletir (M8).

Consumer group kullanılır: yeniden başlatmada acknowledge edilmemiş event'ler
tekrar teslim edilir (kayıp olmaz). drain_once() bilinçli olarak loop'tan ayrı —
testler timing'e bağlı kalmadan tek seferde tüketebilir.
"""
import json

import redis.asyncio as aioredis
import structlog
from redis.exceptions import ResponseError

from app.core import clickhouse
from app.services.trace_collector import STREAM

logger = structlog.get_logger()

GROUP = "trace_consumers"
CONSUMER = "c1"


async def ensure_group(redis: aioredis.Redis) -> None:
    """Consumer group'u oluşturur (varsa sessizce geçer). Stream yoksa MKSTREAM ile yaratır."""
    try:
        await redis.xgroup_create(STREAM, GROUP, id="$", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


class TraceConsumer:
    def __init__(self, redis: aioredis.Redis, ws_manager=None) -> None:
        self.redis = redis
        self.ws_manager = ws_manager
        self._running = False

    async def _handle(self, event: dict) -> None:
        await clickhouse.insert_event(event)
        if event.get("type") == "agent_end":
            await clickhouse.insert_trace_from_end(event)
        if self.ws_manager is not None:
            await self.ws_manager.broadcast(event["organization_id"], event)

    async def drain_once(self, count: int = 200, block_ms: int = 0) -> int:
        """Bekleyen yeni event'leri tek seferde işler. İşlenen event sayısını döner."""
        resp = await self.redis.xreadgroup(
            GROUP, CONSUMER, {STREAM: ">"}, count=count, block=block_ms or None
        )
        if not resp:
            return 0

        processed = 0
        for _stream, entries in resp:
            ack_ids = []
            for entry_id, fields in entries:
                try:
                    event = json.loads(fields["data"])
                    await self._handle(event)
                except Exception as exc:  # bir event patlasa da diğerleri işlensin
                    logger.error("trace_consumer.handle_failed", error=str(exc))
                ack_ids.append(entry_id)
                processed += 1
            if ack_ids:
                await self.redis.xack(STREAM, GROUP, *ack_ids)
        return processed

    async def run(self) -> None:
        """Lifespan'de başlatılan sonsuz tüketim döngüsü."""
        self._running = True
        logger.info("trace_consumer.started")
        while self._running:
            try:
                await self.drain_once(block_ms=2000)
            except Exception as exc:
                logger.error("trace_consumer.loop_error", error=str(exc))

    def stop(self) -> None:
        self._running = False
