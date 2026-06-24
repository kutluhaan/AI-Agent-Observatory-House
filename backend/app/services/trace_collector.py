"""
Trace Collector — agent/LLM event'lerini Redis Stream'e yazar (M8).

Tasarım: olaylar tek bir global stream'e (observatory:traces) yazılır; her kayıt
organization_id taşır. İzolasyon org_id ile sağlanır — consumer ClickHouse'a org_id
ile yazar, WebSocket sadece ilgili org'a iletir, sorgular org_id ile filtreler.
(Spec org-bazlı stream key'i öneriyordu; tek stream + org_id consumer'ı basit ve
doğru tutar — bilinçli sadeleştirme.)

Yazma noktası kasıtlı olarak hızlı: sadece XADD. ClickHouse persist + WebSocket
iletimi arka plandaki Trace Consumer tarafından yapılır.
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis

STREAM = "observatory:traces"
STREAM_MAXLEN = 100_000  # yaklaşık tavan — eski event'ler trim edilir

# Bilinen event tipleri (referans):
#   agent_start / agent_end
#   llm_call_start / llm_call_end
#   tool_call_start / tool_call_end
#   reasoning / hitl_requested / error


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def _xadd(redis: aioredis.Redis, event: dict[str, Any]) -> None:
    await redis.xadd(
        STREAM,
        {"data": json.dumps(event)},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )


@dataclass
class Tracer:
    """
    Tek bir trace (çalıştırma) için event üretici.

    Kullanım:
        tracer = Tracer(redis, org_id, name="test-completion")
        await tracer.start()
        await tracer.event("llm_call_start", {"model": "gpt-4o"})
        ...
        await tracer.end(status="completed")

    Multi-agent: parent_trace_id verilirse her event'e eklenir; UI bağlantıyı izleyebilir.
    end() is idempotent — safe to call in both success and error paths.
    """
    redis: aioredis.Redis
    organization_id: str
    name: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=_now_iso)
    parent_trace_id: str | None = None
    metadata: dict[str, Any] | None = None  # it.6: agent_start payload'ına eklenir (ör. prompt_version)
    _ended: bool = field(default=False, init=False, repr=False)

    def _base(self, type_: str, payload: dict[str, Any] | None, ts: str) -> dict[str, Any]:
        event: dict[str, Any] = {
            "trace_id": self.trace_id,
            "organization_id": self.organization_id,
            "type": type_,
            "timestamp": ts,
            "payload": payload or {},
        }
        if self.parent_trace_id:
            event["parent_trace_id"] = self.parent_trace_id
        return event

    async def start(self) -> None:
        await _xadd(self.redis, self._base("agent_start", {"name": self.name, **(self.metadata or {})}, self.started_at))

    async def event(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        await _xadd(self.redis, self._base(type_, payload, _now_iso()))

    async def end(self, status: str = "completed", payload: dict[str, Any] | None = None) -> None:
        if self._ended:
            return
        self._ended = True
        ended = _now_iso()
        end_payload: dict[str, Any] = {
            "name": self.name,
            "status": status,
            "started_at": self.started_at,
            "ended_at": ended,
        }
        if payload:
            end_payload.update(payload)
        await _xadd(self.redis, self._base("agent_end", end_payload, ended))
