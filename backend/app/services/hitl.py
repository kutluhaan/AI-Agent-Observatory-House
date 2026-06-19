"""
HITL Engine — Human-in-the-Loop request lifecycle (M10).

Akış:
  1. Runner create_request() ile Redis'e metadata yazar ve request_id alır.
  2. Runner SSE üzerinden hitl_requested event'i yield eder.
  3. Runner wait_for_resolution() ile bloklar (asyncio.Event).
  4. REST endpoint /hitl/{id}/approve|reject|modify çağrılınca resolve() Event'i set eder.
  5. wait_for_resolution() HITLResolution döner.
  6. Runner action'a göre devam eder (approved/modified) veya HITLRejectedError fırlatır.
  7. Timeout (10 dk): HITLTimeoutError fırlatılır, Redis kaydı TTL ile silinir.

split API (create_request + wait_for_resolution):
  Stream path'te SSE event'leri arasında yield yapabilmek için iki ayrı adım.

Singleton: init_hitl_engine() startup'ta bir kez; get_hitl_engine() her yerden.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()

HITL_TIMEOUT = 600           # 10 dakika (saniye)
_KEY_PREFIX = "hitl:"
_KEY_TTL_AFTER_RESOLVE = 120  # çözümlendikten sonra 2 dk daha Redis'te kalsın (audit)


@dataclass
class HITLRequest:
    request_id: str
    trace_id: str
    org_id: str
    tool_name: str
    tool_arguments: dict[str, Any]
    status: str           # pending | approved | rejected | modified
    created_at: str
    expires_at: str
    reason: str | None = None
    modified_arguments: dict[str, Any] | None = None


@dataclass
class HITLResolution:
    action: Literal["approved", "rejected", "modified"]
    modified_arguments: dict[str, Any] | None = None
    reason: str | None = None


class HITLNotFoundError(Exception):
    """request_id Redis'te bulunamadı (expired veya hiç oluşturulmadı)."""


class HITLAlreadyResolvedError(Exception):
    """İstek zaten çözümlendi; tekrar approve/reject yapılamaz."""

    def __init__(self, request_id: str, current_status: str) -> None:
        self.current_status = current_status
        super().__init__(f"HITL request '{request_id}' is already '{current_status}'.")


class HITLEngine:
    """
    In-flight HITL request'leri yönetir.

    _pending: request_id → (asyncio.Event, list[HITLResolution])
    list tek eleman taşır — mutable container olarak kullanılır.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis
        self._pending: dict[str, tuple[asyncio.Event, list[HITLResolution]]] = {}

    # ─── Runner tarafı ────────────────────────────────────

    async def create_request(
        self,
        *,
        trace_id: str,
        org_id: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
    ) -> str:
        """
        HITL isteği oluşturur; Redis'e yazar ve in-memory Event kaydeder.
        request_id döner — runner bunu SSE event'ine ekler.
        """
        request_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=HITL_TIMEOUT)

        data = {
            "request_id": request_id,
            "trace_id": trace_id,
            "org_id": org_id,
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "status": "pending",
            "created_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "reason": None,
            "modified_arguments": None,
        }
        await self.redis.setex(
            f"{_KEY_PREFIX}{request_id}",
            HITL_TIMEOUT,
            json.dumps(data),
        )

        event: asyncio.Event = asyncio.Event()
        self._pending[request_id] = (event, [])

        logger.info("hitl.created", request_id=request_id, tool=tool_name, trace_id=trace_id)
        return request_id

    async def wait_for_resolution(self, request_id: str) -> HITLResolution:
        """
        İnsan kararını bekler. Çözülünce HITLResolution döner.

        Raises:
            HITLTimeoutError: 10 dakika içinde yanıt gelmezse.
        """
        from app.services.agent.base import HITLTimeoutError

        entry = self._pending.get(request_id)
        if entry is None:
            raise HITLTimeoutError(request_id)

        event, resolutions = entry
        try:
            await asyncio.wait_for(event.wait(), timeout=HITL_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("hitl.timeout", request_id=request_id)
            raise HITLTimeoutError(request_id)
        finally:
            self._pending.pop(request_id, None)

        return resolutions[0]

    # ─── API endpoint tarafı ──────────────────────────────

    async def resolve(
        self,
        request_id: str,
        action: Literal["approved", "rejected", "modified"],
        *,
        modified_arguments: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> HITLRequest:
        """
        Endpoint'ten çağrılır. Redis kaydını günceller, beklenen runner'ı uyandırır.

        Returns:
            Güncellenmiş HITLRequest.

        Raises:
            HITLNotFoundError: request_id bulunamadı veya expire oldu.
            HITLAlreadyResolvedError: istek zaten çözümlendi.
        """
        key = f"{_KEY_PREFIX}{request_id}"
        raw = await self.redis.get(key)
        if raw is None:
            raise HITLNotFoundError(f"HITL request '{request_id}' not found or expired.")

        data: dict[str, Any] = json.loads(raw)
        if data["status"] != "pending":
            raise HITLAlreadyResolvedError(request_id, data["status"])

        data["status"] = action
        data["reason"] = reason
        data["modified_arguments"] = modified_arguments

        await self.redis.setex(key, _KEY_TTL_AFTER_RESOLVE, json.dumps(data))

        resolution = HITLResolution(
            action=action,
            modified_arguments=modified_arguments,
            reason=reason,
        )

        entry = self._pending.get(request_id)
        if entry:
            event, resolutions = entry
            resolutions.append(resolution)
            event.set()
            logger.info("hitl.resolved", request_id=request_id, action=action)
        else:
            # Runner zaten timeout'a uğramış; Redis kaydını yine de güncelledik.
            logger.warning("hitl.resolve.no_waiter", request_id=request_id, action=action)

        return _data_to_request(data)

    async def get(self, request_id: str) -> HITLRequest | None:
        """Redis'ten istek bilgisini okur. Yoksa None döner."""
        raw = await self.redis.get(f"{_KEY_PREFIX}{request_id}")
        if raw is None:
            return None
        return _data_to_request(json.loads(raw))


def _data_to_request(data: dict[str, Any]) -> HITLRequest:
    return HITLRequest(
        request_id=data["request_id"],
        trace_id=data["trace_id"],
        org_id=data["org_id"],
        tool_name=data["tool_name"],
        tool_arguments=data["tool_arguments"],
        status=data["status"],
        created_at=data["created_at"],
        expires_at=data["expires_at"],
        reason=data.get("reason"),
        modified_arguments=data.get("modified_arguments"),
    )


# ─── Singleton ────────────────────────────────────────────

_engine: HITLEngine | None = None


def init_hitl_engine(redis: aioredis.Redis) -> HITLEngine:
    """Startup'ta bir kez çağrılır."""
    global _engine
    _engine = HITLEngine(redis)
    return _engine


def get_hitl_engine() -> HITLEngine:
    if _engine is None:
        raise RuntimeError("HITLEngine is not initialized. Call init_hitl_engine() at startup.")
    return _engine
