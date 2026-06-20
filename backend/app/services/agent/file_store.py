"""
Agent dosya sistemi deposu (Faz 3).

Her agent'ın izole sanal FS'i (agent_files tablosu). Tool-facing fonksiyonlar
kendi DB session'larını açar (streaming sırasında istek session'ı kapanmış
olabileceğinden) ve kullanıcı dostu string döner. Endpoint-facing fonksiyonlar
(list_all/get_one) verilen session'ı kullanır.

Budama: agent başına MAX_FILES dosya / MAX_TOTAL_BYTES bayt; aşılırsa en eski
güncellenen dosyalar silinir.
"""
from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.agent_file import AgentFile

logger = structlog.get_logger()

MAX_FILES = 500
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB


def normalize_path(path: str) -> str:
    """Yolu normalize eder; geçersizse ValueError fırlatır."""
    p = re.sub(r"/+", "/", (path or "").strip().strip("/"))
    if not p:
        raise ValueError("path cannot be empty")
    if len(p) > 1000:
        raise ValueError("path is too long")
    for part in p.split("/"):
        if part in ("", ".", ".."):
            raise ValueError("path must not contain '.', '..' or empty segments")
    return p


async def _get(db: AsyncSession, agent_id: uuid.UUID, path: str) -> AgentFile | None:
    res = await db.execute(
        select(AgentFile).where(AgentFile.agent_id == agent_id, AgentFile.path == path)
    )
    return res.scalar_one_or_none()


async def _prune(db: AsyncSession, agent_id: uuid.UUID) -> int:
    """Limitler aşıldıysa en eski güncellenen dosyaları siler. Silinen sayısını döner."""
    rows = (await db.execute(
        select(AgentFile)
        .where(AgentFile.agent_id == agent_id, AgentFile.is_dir == False)  # noqa: E712
        .order_by(AgentFile.updated_at.asc())
    )).scalars().all()
    total = sum(r.size_bytes for r in rows)
    count = len(rows)
    pruned = 0
    i = 0
    while (count > MAX_FILES or total > MAX_TOTAL_BYTES) and i < len(rows):
        r = rows[i]
        i += 1
        total -= r.size_bytes
        count -= 1
        await db.delete(r)
        pruned += 1
    if pruned:
        await db.commit()
        logger.warning("agent_files.pruned", agent_id=str(agent_id), pruned=pruned)
    return pruned


# ─── Tool-facing (kendi session'ı, string döner) ──────────

async def write_file(agent_id, org_id, path: str, content: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[write_file error: {e}]"
    content = content or ""
    size = len(content.encode("utf-8"))
    async with AsyncSessionLocal() as db:
        existing = await _get(db, agent_id, path)
        if existing and existing.is_dir:
            return f"[write_file error: '{path}' is a directory]"
        if existing:
            existing.content = content
            existing.size_bytes = size
        else:
            db.add(AgentFile(
                agent_id=agent_id, organization_id=org_id, path=path,
                is_dir=False, content=content, size_bytes=size,
            ))
        await db.commit()
        pruned = await _prune(db, agent_id)
    msg = f"Wrote '{path}' ({len(content)} chars)."
    if pruned:
        msg += f" Pruned {pruned} old file(s) to stay within storage limits."
    return msg


async def read_file(agent_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[read_file error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, agent_id, path)
    if f is None or f.is_dir:
        return f"[read_file error: file '{path}' not found]"
    return f.content or ""


async def modify_file(agent_id, path: str, old_string: str, new_string: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[modify_file error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, agent_id, path)
        if f is None or f.is_dir:
            return f"[modify_file error: file '{path}' not found]"
        content = f.content or ""
        if old_string not in content:
            return f"[modify_file error: the text to replace was not found in '{path}']"
        new_content = content.replace(old_string, new_string)
        f.content = new_content
        f.size_bytes = len(new_content.encode("utf-8"))
        await db.commit()
    return f"Modified '{path}'."


async def delete_file(agent_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[delete_file error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, agent_id, path)
        if f is None:
            return f"[delete_file error: '{path}' not found]"
        if f.is_dir:
            child = (await db.execute(
                select(AgentFile).where(
                    AgentFile.agent_id == agent_id,
                    AgentFile.path.like(f"{path}/%"),
                ).limit(1)
            )).scalar_one_or_none()
            if child is not None:
                return f"[delete_file error: directory '{path}' is not empty]"
        await db.delete(f)
        await db.commit()
    return f"Deleted '{path}'."


async def list_files(agent_id, path: str | None = None) -> str:
    prefix = ""
    if path:
        try:
            prefix = normalize_path(path) + "/"
        except ValueError as e:
            return f"[list_files error: {e}]"
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AgentFile).where(AgentFile.agent_id == agent_id).order_by(AgentFile.path)
        )).scalars().all()
    items = [r for r in rows if not prefix or r.path.startswith(prefix)]
    if not items:
        return "(no files yet)" if not prefix else f"(nothing under '{path}')"
    lines = []
    for r in items:
        if r.is_dir:
            lines.append(f"[dir]  {r.path}/")
        else:
            lines.append(f"[file] {r.path} ({r.size_bytes} bytes)")
    return "\n".join(lines)


async def make_directory(agent_id, org_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[make_directory error: {e}]"
    async with AsyncSessionLocal() as db:
        existing = await _get(db, agent_id, path)
        if existing is not None:
            return f"[make_directory error: '{path}' already exists]"
        db.add(AgentFile(
            agent_id=agent_id, organization_id=org_id, path=path,
            is_dir=True, content=None, size_bytes=0,
        ))
        await db.commit()
    return f"Created directory '{path}'."


async def search_files(agent_id, query: str) -> str:
    if not query or not query.strip():
        return "[search_files error: query cannot be empty]"
    q = query.lower()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AgentFile).where(
                AgentFile.agent_id == agent_id, AgentFile.is_dir == False,  # noqa: E712
            )
        )).scalars().all()
    matches: list[str] = []
    for r in rows:
        content = r.content or ""
        in_name = q in r.path.lower()
        idx = content.lower().find(q)
        if in_name or idx >= 0:
            if idx >= 0:
                snippet = content[max(0, idx - 30): idx + 50].replace("\n", " ").strip()
                matches.append(f"{r.path}  …{snippet}…")
            else:
                matches.append(f"{r.path}  (filename match)")
    if not matches:
        return f"No files matching '{query}'."
    return f"{len(matches)} match(es):\n" + "\n".join(matches[:20])


async def move_file(agent_id, source: str, destination: str) -> str:
    try:
        src = normalize_path(source)
        dst = normalize_path(destination)
    except ValueError as e:
        return f"[move_file error: {e}]"
    if src == dst:
        return "[move_file error: source and destination are the same]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, agent_id, src)
        if f is None:
            return f"[move_file error: '{src}' not found]"
        if await _get(db, agent_id, dst) is not None:
            return f"[move_file error: '{dst}' already exists]"
        if f.is_dir:
            children = (await db.execute(
                select(AgentFile).where(
                    AgentFile.agent_id == agent_id,
                    AgentFile.path.like(f"{src}/%"),
                )
            )).scalars().all()
            for c in children:
                c.path = dst + c.path[len(src):]
        f.path = dst
        await db.commit()
    return f"Moved '{src}' to '{dst}'."


# ─── Endpoint-facing (verilen session) ────────────────────

async def list_all(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentFile]:
    res = await db.execute(
        select(AgentFile).where(AgentFile.agent_id == agent_id).order_by(AgentFile.path)
    )
    return list(res.scalars().all())


async def get_one(db: AsyncSession, agent_id: uuid.UUID, path: str) -> AgentFile | None:
    return await _get(db, agent_id, path)
