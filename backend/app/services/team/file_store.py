"""
Ekip ortak dosya sistemi deposu (E) — agent file_store'un ekip karşılığı.

Bir ekipteki tüm üyeler aynı sanal FS'i (team_files) paylaşır. Tool-facing fonksiyonlar
kendi session'ını açar; endpoint-facing (list_all/get_one) verilen session'ı kullanır.
Mantık agent file_store ile aynıdır; yalnız team_id ile scope'lanır.
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.team_file import TeamFile
from app.services.agent.file_store import MAX_FILES, MAX_TOTAL_BYTES, normalize_path

logger = structlog.get_logger()


async def _get(db: AsyncSession, team_id: uuid.UUID, path: str) -> TeamFile | None:
    return (await db.execute(
        select(TeamFile).where(TeamFile.team_id == team_id, TeamFile.path == path)
    )).scalar_one_or_none()


async def _prune(db: AsyncSession, team_id: uuid.UUID) -> int:
    rows = (await db.execute(
        select(TeamFile).where(TeamFile.team_id == team_id, TeamFile.is_dir == False)  # noqa: E712
        .order_by(TeamFile.updated_at.asc())
    )).scalars().all()
    total = sum(r.size_bytes for r in rows)
    count = len(rows)
    pruned = 0
    i = 0
    while (count > MAX_FILES or total > MAX_TOTAL_BYTES) and i < len(rows):
        r = rows[i]; i += 1
        total -= r.size_bytes; count -= 1
        await db.delete(r); pruned += 1
    if pruned:
        await db.commit()
    return pruned


async def write_file(team_id, org_id, path: str, content: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[write_file error: {e}]"
    content = content or ""
    size = len(content.encode("utf-8"))
    async with AsyncSessionLocal() as db:
        existing = await _get(db, team_id, path)
        if existing and existing.is_dir:
            return f"[write_file error: '{path}' is a directory]"
        if existing:
            existing.content = content
            existing.size_bytes = size
        else:
            db.add(TeamFile(team_id=team_id, organization_id=org_id, path=path,
                            is_dir=False, content=content, size_bytes=size))
        await db.commit()
        pruned = await _prune(db, team_id)
    msg = f"Wrote '{path}' ({len(content)} chars) to team files."
    if pruned:
        msg += f" Pruned {pruned} old file(s)."
    return msg


async def read_file(team_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[read_file error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, team_id, path)
    if f is None or f.is_dir:
        return f"[read_file error: file '{path}' not found]"
    return f.content or ""


async def modify_file(team_id, path: str, old_string: str, new_string: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[modify_file error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, team_id, path)
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


async def delete_file(team_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[delete_file error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, team_id, path)
        if f is None:
            return f"[delete_file error: '{path}' not found]"
        if f.is_dir:
            child = (await db.execute(select(TeamFile).where(
                TeamFile.team_id == team_id, TeamFile.path.like(f"{path}/%")).limit(1))).scalar_one_or_none()
            if child is not None:
                return f"[delete_file error: directory '{path}' is not empty]"
        await db.delete(f)
        await db.commit()
    return f"Deleted '{path}'."


async def remove_folder(team_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[remove_folder error: {e}]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, team_id, path)
        if f is not None and not f.is_dir:
            return f"[remove_folder error: '{path}' is a file — use delete_file]"
        children = (await db.execute(select(TeamFile).where(
            TeamFile.team_id == team_id, TeamFile.path.like(f"{path}/%")))).scalars().all()
        if f is None and not children:
            return f"[remove_folder error: '{path}' not found]"
        for c in children:
            await db.delete(c)
        if f is not None:
            await db.delete(f)
        await db.commit()
    return f"Removed folder '{path}' and {len(children)} item(s)."


async def list_files(team_id, path: str | None = None) -> str:
    prefix = ""
    if path:
        try:
            prefix = normalize_path(path) + "/"
        except ValueError as e:
            return f"[list_files error: {e}]"
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(TeamFile).where(TeamFile.team_id == team_id).order_by(TeamFile.path))).scalars().all()
    items = [r for r in rows if not prefix or r.path.startswith(prefix)]
    if not items:
        return "(no files yet)" if not prefix else f"(nothing under '{path}')"
    return "\n".join(f"[dir]  {r.path}/" if r.is_dir else f"[file] {r.path} ({r.size_bytes} bytes)" for r in items)


async def make_directory(team_id, org_id, path: str) -> str:
    try:
        path = normalize_path(path)
    except ValueError as e:
        return f"[make_directory error: {e}]"
    async with AsyncSessionLocal() as db:
        if await _get(db, team_id, path) is not None:
            return f"[make_directory error: '{path}' already exists]"
        db.add(TeamFile(team_id=team_id, organization_id=org_id, path=path, is_dir=True, content=None, size_bytes=0))
        await db.commit()
    return f"Created directory '{path}'."


async def search_files(team_id, query: str) -> str:
    if not query or not query.strip():
        return "[search_files error: query cannot be empty]"
    q = query.lower()
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(TeamFile).where(
            TeamFile.team_id == team_id, TeamFile.is_dir == False))).scalars().all()  # noqa: E712
    matches: list[str] = []
    for r in rows:
        content = r.content or ""
        idx = content.lower().find(q)
        if q in r.path.lower() or idx >= 0:
            if idx >= 0:
                snippet = content[max(0, idx - 30): idx + 50].replace("\n", " ").strip()
                matches.append(f"{r.path}  …{snippet}…")
            else:
                matches.append(f"{r.path}  (filename match)")
    if not matches:
        return f"No files matching '{query}'."
    return f"{len(matches)} match(es):\n" + "\n".join(matches[:20])


async def move_file(team_id, source: str, destination: str) -> str:
    try:
        src = normalize_path(source)
        dst = normalize_path(destination)
    except ValueError as e:
        return f"[move_file error: {e}]"
    if src == dst:
        return "[move_file error: source and destination are the same]"
    async with AsyncSessionLocal() as db:
        f = await _get(db, team_id, src)
        if f is None:
            return f"[move_file error: '{src}' not found]"
        if await _get(db, team_id, dst) is not None:
            return f"[move_file error: '{dst}' already exists]"
        if f.is_dir:
            children = (await db.execute(select(TeamFile).where(
                TeamFile.team_id == team_id, TeamFile.path.like(f"{src}/%")))).scalars().all()
            for c in children:
                c.path = dst + c.path[len(src):]
        f.path = dst
        await db.commit()
    return f"Moved '{src}' to '{dst}'."


# ─── Endpoint-facing ──────────────────────────────────────

async def list_all(db: AsyncSession, team_id: uuid.UUID) -> list[TeamFile]:
    return list((await db.execute(
        select(TeamFile).where(TeamFile.team_id == team_id).order_by(TeamFile.path))).scalars().all())


async def get_one(db: AsyncSession, team_id: uuid.UUID, path: str) -> TeamFile | None:
    return await _get(db, team_id, path)
