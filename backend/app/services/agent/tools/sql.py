"""
Veritabanı & SQL tool'ları — SQL kategorisi (loop it.8)

sql_query  : verilen SELECT sorgusunu SALT-OKUNUR çalıştırır
sql_schema : bağlı DB'deki tabloları + sütunları listeler (keşif)
sql_sample : bir tablodan örnek satırlar (SELECT * LIMIT n)

Güvenlik: org'da yapılandırılmış (DbConnection, DSN şifreli) bir PostgreSQL'e
asyncpg ile bağlanır; sorgu **readonly transaction** içinde + statement_timeout +
satır limiti ile çalışır. Yazma ifadeleri DB seviyesinde reddedilir; ayrıca tek
SELECT/WITH ifadesi şartı uygulanır. Tool'lar exception fırlatmaz.
"""
from __future__ import annotations

import re

import asyncpg
from sqlalchemy import select

from app.core.encryption import decrypt_value
from app.models.db_connection import DbConnection
from app.services.agent.registry import ToolContext, ToolRegistry

_NO_CONN = "[sql error: bağlı veritabanı yok — Veritabanları'ndan bir bağlantı ekle]"
_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$")  # tablo[/şema.tablo]
_MAX_ROWS = 50


async def _resolve_conn(ctx: ToolContext, name: str | None) -> DbConnection | None:
    q = select(DbConnection).where(DbConnection.organization_id == ctx.org_id, DbConnection.is_active.is_(True))
    q = q.where(DbConnection.name == name) if name else q.order_by(DbConnection.created_at.asc())
    return (await ctx.db.execute(q)).scalars().first()


def _normalize_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")


async def _run_readonly(dsn: str, query: str, max_rows: int = _MAX_ROWS) -> list[dict]:
    conn = await asyncpg.connect(_normalize_dsn(dsn), timeout=10)
    try:
        await conn.execute("SET statement_timeout = 8000")  # 8sn
        async with conn.transaction(readonly=True):  # yazma DB seviyesinde reddedilir
            rows = await conn.fetch(query)
    finally:
        await conn.close()
    return [dict(r) for r in rows[:max_rows]]


def _fmt(rows: list[dict]) -> str:
    if not rows:
        return "Sonuç yok (0 satır)."
    cols = list(rows[0].keys())
    head = " | ".join(cols)
    sep = " | ".join("---" for _ in cols)
    body = "\n".join(" | ".join(str(r.get(c, "")) for c in cols) for r in rows)
    return f"{len(rows)} satır:\n\n{head}\n{sep}\n{body}"


def register_sql_tools() -> None:
    if "sql_query" in ToolRegistry.all_names():
        return

    @ToolRegistry.register(
        "sql_query",
        "Run a READ-ONLY SQL query (single SELECT or WITH statement) against the connected PostgreSQL database. "
        "Writes are blocked. Returns up to 50 rows as a table.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "A single SELECT/WITH SQL statement."},
            "connection": {"type": "string", "description": "Connection name (optional; default connection if omitted)."},
        }, "required": ["query"]},
    )
    async def sql_query(ctx: ToolContext, query: str, connection: str | None = None) -> str:
        # Önce sorguyu doğrula (DB'ye gerek yok) — salt-okunur, tek ifade
        q = query.strip().rstrip(";").strip()
        if ";" in q:
            return "[sql error: tek bir SELECT/WITH ifadesi çalıştır (';' ile çoklu ifade yok)]"
        low = q.lower()
        if not (low.startswith("select") or low.startswith("with")):
            return "[sql error: sadece SELECT/WITH okuma sorgularına izin var]"
        if ctx.db is None:
            return "[sql error: no db context]"
        c = await _resolve_conn(ctx, connection)
        if c is None:
            return _NO_CONN
        try:
            return _fmt(await _run_readonly(decrypt_value(c.encrypted_dsn), q))
        except Exception as exc:  # noqa: BLE001
            return f"[sql error: {exc}]"

    @ToolRegistry.register(
        "sql_schema",
        "List tables and their columns/types in the connected PostgreSQL database (public schema). Use to discover structure.",
        {"type": "object", "properties": {
            "connection": {"type": "string", "description": "Connection name (optional)."},
        }, "required": []},
    )
    async def sql_schema(ctx: ToolContext, connection: str | None = None) -> str:
        if ctx.db is None:
            return "[sql error: no db context]"
        c = await _resolve_conn(ctx, connection)
        if c is None:
            return _NO_CONN
        q = ("SELECT table_name, column_name, data_type FROM information_schema.columns "
             "WHERE table_schema='public' ORDER BY table_name, ordinal_position")
        try:
            rows = await _run_readonly(decrypt_value(c.encrypted_dsn), q, max_rows=500)
        except Exception as exc:  # noqa: BLE001
            return f"[sql error: {exc}]"
        if not rows:
            return "public şemasında tablo yok."
        by_table: dict[str, list[str]] = {}
        for r in rows:
            by_table.setdefault(r["table_name"], []).append(f"{r['column_name']} {r['data_type']}")
        return "\n".join(f"- **{t}**: " + ", ".join(cols) for t, cols in by_table.items())

    @ToolRegistry.register(
        "sql_sample",
        "Get sample rows from a table (SELECT * ... LIMIT n) in the connected PostgreSQL database.",
        {"type": "object", "properties": {
            "table": {"type": "string", "description": "Table name (optionally schema.table)."},
            "limit": {"type": "integer", "description": "Rows to return (1-50). Default 10."},
            "connection": {"type": "string", "description": "Connection name (optional)."},
        }, "required": ["table"]},
    )
    async def sql_sample(ctx: ToolContext, table: str, limit: int = 10, connection: str | None = None) -> str:
        if ctx.db is None:
            return "[sql error: no db context]"
        if not _IDENT.match(table.strip()):
            return "[sql error: geçersiz tablo adı]"
        c = await _resolve_conn(ctx, connection)
        if c is None:
            return _NO_CONN
        n = max(1, min(int(limit or 10), _MAX_ROWS))
        try:
            return _fmt(await _run_readonly(decrypt_value(c.encrypted_dsn), f"SELECT * FROM {table.strip()} LIMIT {n}", n))
        except Exception as exc:  # noqa: BLE001
            return f"[sql error: {exc}]"
