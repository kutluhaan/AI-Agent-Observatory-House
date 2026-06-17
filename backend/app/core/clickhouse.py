"""
ClickHouse Client — trace/event kalıcı deposu (M8).

clickhouse-connect senkron çalışır; M4'teki Resend deseni gibi tüm çağrılar
asyncio.to_thread ile sarmalanır — event loop bloklanmaz.

Şema Alembic'le yönetilmez (o Postgres içindir). init_schema() lifespan
startup'ta CREATE TABLE IF NOT EXISTS çalıştırır.
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_client = None


def _get_client():
    """Singleton senkron ClickHouse client (HTTP arabirimi, port 8123)."""
    global _client
    if _client is None:
        import clickhouse_connect

        _client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_http_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_db,
        )
    return _client


def close_clickhouse() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)  # ClickHouse naive UTC saklar
    return dt


# ─── Schema ───────────────────────────────────────────────

async def init_schema() -> None:
    """traces + events tablolarını oluşturur (idempotent)."""
    retention = int(settings.trace_retention_days)

    traces_ddl = """
    CREATE TABLE IF NOT EXISTS traces (
        trace_id        UUID,
        organization_id UUID,
        name            String,
        status          String,
        started_at      DateTime64(3),
        ended_at        Nullable(DateTime64(3)),
        created_at      DateTime64(3) DEFAULT now64(3)
    ) ENGINE = MergeTree()
    ORDER BY (organization_id, started_at, trace_id)
    """

    events_ddl = f"""
    CREATE TABLE IF NOT EXISTS events (
        event_id        UUID DEFAULT generateUUIDv4(),
        trace_id        UUID,
        organization_id UUID,
        type            String,
        payload         String,
        created_at      DateTime64(3) DEFAULT now64(3)
    ) ENGINE = MergeTree()
    ORDER BY (organization_id, trace_id, created_at)
    TTL toDateTime(created_at) + INTERVAL {retention} DAY
    """

    await asyncio.to_thread(_get_client().command, traces_ddl)
    await asyncio.to_thread(_get_client().command, events_ddl)
    logger.info("clickhouse.schema_ready", retention_days=retention)


# ─── Insert ───────────────────────────────────────────────

async def insert_event(event: dict[str, Any]) -> None:
    """Tek bir event'i events tablosuna yazar."""
    row = [
        uuid.UUID(event["trace_id"]),
        uuid.UUID(event["organization_id"]),
        event["type"],
        json.dumps(event.get("payload", {})),
        _parse_ts(event.get("timestamp")) or datetime.now(UTC).replace(tzinfo=None),
    ]
    await asyncio.to_thread(
        _get_client().insert,
        "events",
        [row],
        column_names=["trace_id", "organization_id", "type", "payload", "created_at"],
    )


async def insert_trace_from_end(event: dict[str, Any]) -> None:
    """agent_end event'inden traces tablosuna bir satır yazar."""
    payload = event.get("payload", {})
    row = [
        uuid.UUID(event["trace_id"]),
        uuid.UUID(event["organization_id"]),
        payload.get("name", ""),
        payload.get("status", "completed"),
        _parse_ts(payload.get("started_at")) or datetime.now(UTC).replace(tzinfo=None),
        _parse_ts(payload.get("ended_at")),
    ]
    await asyncio.to_thread(
        _get_client().insert,
        "traces",
        [row],
        column_names=["trace_id", "organization_id", "name", "status", "started_at", "ended_at"],
    )


# ─── Query ────────────────────────────────────────────────

async def query_traces(
    organization_id: uuid.UUID,
    limit: int = 50,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Org'un trace listesi — en yeni önce."""
    where = "organization_id = {org:UUID}"
    params: dict[str, Any] = {"org": str(organization_id), "lim": limit}
    if status:
        where += " AND status = {status:String}"
        params["status"] = status

    sql = f"""
        SELECT trace_id, name, status, started_at, ended_at
        FROM traces
        WHERE {where}
        ORDER BY started_at DESC
        LIMIT {{lim:UInt32}}
    """
    result = await asyncio.to_thread(_get_client().query, sql, parameters=params)
    return [
        {
            "trace_id": str(r[0]),
            "name": r[1],
            "status": r[2],
            "started_at": r[3].isoformat() if r[3] else None,
            "ended_at": r[4].isoformat() if r[4] else None,
        }
        for r in result.result_rows
    ]


async def get_trace(
    organization_id: uuid.UUID,
    trace_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Tek trace + event'leri (timeline). Başka org'a aitse None döner."""
    params = {"org": str(organization_id), "tid": str(trace_id)}

    trace_rows = await asyncio.to_thread(
        _get_client().query,
        """
        SELECT trace_id, name, status, started_at, ended_at
        FROM traces
        WHERE organization_id = {org:UUID} AND trace_id = {tid:UUID}
        LIMIT 1
        """,
        parameters=params,
    )
    if not trace_rows.result_rows:
        return None
    t = trace_rows.result_rows[0]

    event_rows = await asyncio.to_thread(
        _get_client().query,
        """
        SELECT type, payload, created_at
        FROM events
        WHERE organization_id = {org:UUID} AND trace_id = {tid:UUID}
        ORDER BY created_at ASC
        """,
        parameters=params,
    )
    events = [
        {
            "type": r[0],
            "payload": json.loads(r[1]) if r[1] else {},
            "timestamp": r[2].isoformat() if r[2] else None,
        }
        for r in event_rows.result_rows
    ]

    return {
        "trace_id": str(t[0]),
        "name": t[1],
        "status": t[2],
        "started_at": t[3].isoformat() if t[3] else None,
        "ended_at": t[4].isoformat() if t[4] else None,
        "events": events,
    }
