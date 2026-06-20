"""
Skill tool'ları (Faz 4) — talep üzerine bilgi okuma.

Agent'ın skill'i varsa runner bu tool'ları OTOMATİK ekler (kullanıcı tek tek seçmez).
GET /agents/tools listesinde de gösterilmezler (SKILL_TOOL_NAMES ile hariç tutulur).
"""
from __future__ import annotations

from app.services.agent import knowledge_store
from app.services.agent.registry import ToolContext, ToolRegistry

SKILL_TOOL_NAMES = ["list_skills", "read_skill"]


def register_skill_tools() -> None:
    """Idempotent."""
    try:
        ToolRegistry.get("list_skills")
        return
    except KeyError:
        pass

    @ToolRegistry.register(
        name="list_skills",
        description=(
            "List the skills available to you. Skills are reusable guides on how to do specific "
            "tasks. Call this when starting a task to see if a relevant skill exists."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
    )
    async def list_skills(ctx: ToolContext) -> str:
        if ctx.agent_id is None:
            return "No skills available."
        return await knowledge_store.list_skills(ctx.agent_id)

    @ToolRegistry.register(
        name="read_skill",
        description=(
            "Read the full content of a skill by name. Do this before a task the skill covers, "
            "then follow its guidance."
        ),
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Skill name (from list_skills)."}},
            "required": ["name"],
        },
    )
    async def read_skill(ctx: ToolContext, name: str) -> str:
        if ctx.agent_id is None:
            return "[read_skill error: no agent context]"
        return await knowledge_store.read_skill(ctx.agent_id, name)
