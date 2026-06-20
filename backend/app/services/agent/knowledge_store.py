"""
Agent bilgi öğeleri deposu (Faz 4).

load_always_on: constitution/rule/instruction/prompt → system prompt eki (her zaman aktif).
has_skills + list_skills/read_skill: skill'ler talep üzerine okunur (tool ile).

Tool-facing fonksiyonlar kendi session'larını açar; load_always_on/has_skills
_build_runner'ın session'ını kullanır.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.agent_knowledge import AgentKnowledge

_SECTION_HEADERS = {
    "constitution": "# Constitution",
    "rule": "# Rules",
    "instruction": "# Instructions",
    "prompt": "# Additional Guidance",
}
_ORDER = ("constitution", "rule", "instruction", "prompt")


async def load_always_on(db: AsyncSession, agent_id: uuid.UUID) -> str:
    """Her zaman aktif bilgi öğelerini system prompt'a eklenecek metne çevirir."""
    rows = (await db.execute(
        select(AgentKnowledge).where(
            AgentKnowledge.agent_id == agent_id,
            AgentKnowledge.is_active == True,  # noqa: E712
            AgentKnowledge.kind.in_(_ORDER),
        ).order_by(AgentKnowledge.created_at)
    )).scalars().all()
    if not rows:
        return ""

    sections: list[str] = []
    for kind in _ORDER:
        items = [r for r in rows if r.kind == kind]
        if not items:
            continue
        body = "\n\n".join(
            f"## {r.name}\n{r.content}".strip() if r.name else r.content
            for r in items
        )
        sections.append(f"{_SECTION_HEADERS[kind]}\n{body}")
    return "\n\n".join(sections)


async def has_skills(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    count = (await db.execute(
        select(func.count(AgentKnowledge.id)).where(
            AgentKnowledge.agent_id == agent_id,
            AgentKnowledge.is_active == True,  # noqa: E712
            AgentKnowledge.kind == "skill",
        )
    )).scalar() or 0
    return count > 0


# ─── Skill tool'ları (kendi session'ı) ────────────────────

async def list_skills(agent_id) -> str:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AgentKnowledge).where(
                AgentKnowledge.agent_id == agent_id,
                AgentKnowledge.is_active == True,  # noqa: E712
                AgentKnowledge.kind == "skill",
            ).order_by(AgentKnowledge.name)
        )).scalars().all()
    if not rows:
        return "No skills available."
    lines = ["Available skills (use read_skill to load one before a relevant task):"]
    for r in rows:
        first_line = (r.content or "").strip().splitlines()[0] if r.content.strip() else ""
        summary = f" — {first_line[:120]}" if first_line else ""
        lines.append(f"- {r.name}{summary}")
    return "\n".join(lines)


async def read_skill(agent_id, name: str) -> str:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(AgentKnowledge).where(
                AgentKnowledge.agent_id == agent_id,
                AgentKnowledge.is_active == True,  # noqa: E712
                AgentKnowledge.kind == "skill",
                AgentKnowledge.name == name,
            )
        )).scalar_one_or_none()
    if row is None:
        return f"[read_skill error: skill '{name}' not found. Use list_skills to see available skills.]"
    return f"# Skill: {row.name}\n\n{row.content}"


# ─── Endpoint-facing ──────────────────────────────────────

async def list_all(db: AsyncSession, agent_id: uuid.UUID) -> list[AgentKnowledge]:
    res = await db.execute(
        select(AgentKnowledge)
        .where(AgentKnowledge.agent_id == agent_id)
        .order_by(AgentKnowledge.kind, AgentKnowledge.created_at)
    )
    return list(res.scalars().all())
