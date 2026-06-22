"""
Ekip yürütme yardımcıları — F8

- record_message: TeamRunMessage ekler (delegasyon/pano/final timeline'ı, kalıcı).
- build_roster_text: her üyeye verilecek "ekip kadrosu" metni.
- build_member_runner: bir üye agent'ı için rol-farkındalıklı AgentRunner kurar.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.team import TeamMember, TeamRunMessage
from app.services.agent.base import AgentConfig
from app.services.agent.registry import ToolContext
from app.services.agent.runner import AgentRunner
from app.services.agent.tools.files import DESTRUCTIVE_FILE_TOOLS, FILE_TOOL_NAMES
from app.services.providers.factory import get_provider_for_agent
from app.services.team.roles import COORDINATOR, ROLE_LABELS
from app.services.trace_collector import Tracer

# Coordinator delege edebilir; herkes panoyu kullanır
_COORDINATOR_TOOLS = ["delegate", "team_share", "team_board"]
_MEMBER_TOOLS = ["team_share", "team_board"]


async def record_message(
    db: AsyncSession,
    team_run_id: uuid.UUID,
    kind: str,
    content: str,
    *,
    from_role: str | None = None,
    to_role: str | None = None,
    title: str | None = None,
) -> None:
    db.add(TeamRunMessage(
        id=uuid.uuid4(),
        team_run_id=team_run_id,
        kind=kind,
        from_role=from_role,
        to_role=to_role,
        title=title,
        content=content or "",
    ))
    await db.commit()


def build_roster_text(members: list[TeamMember], me_role: str | None) -> str:
    lines = []
    for m in members:
        label = ROLE_LABELS.get(m.role, m.role)
        agent_name = m.agent.name if m.agent else "?"
        tag = " (you)" if m.role == me_role else ""
        lines.append(f"- {label}: agent '{agent_name}'{tag}")
    roster = "\n".join(lines)
    return f"You are part of an agent team. Team roster:\n{roster}"


async def build_member_runner(
    db: AsyncSession,
    redis: Any,
    member: TeamMember,
    members: list[TeamMember],
    *,
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    team_run_id: uuid.UUID,
    parent_trace_id: str | None = None,
) -> AgentRunner:
    """Bir ekip üyesi için rol promptu + kadro + ekip tool'larıyla AgentRunner kurar."""
    agent = (await db.execute(
        select(Agent).where(Agent.id == member.agent_id, Agent.organization_id == org_id)
    )).scalar_one_or_none()
    if agent is None:
        raise ValueError(f"Team member agent '{member.agent_id}' not found.")

    is_coordinator = member.role == COORDINATOR
    roster = build_roster_text(members, member.role)
    system_prompt = (
        f"{agent.system_prompt}\n\n"
        f"--- TEAM ROLE: {ROLE_LABELS.get(member.role, member.role)} ---\n"
        f"{member.role_prompt}\n\n{roster}"
    )

    # Üyenin kendi tool'ları + ekip tool'ları (+ FS açıksa dosya tool'ları)
    tools = list(agent.tool_names or [])
    hitl = [n for n in (agent.hitl_tool_names or []) if n != "ask_user"]
    if agent.file_system_enabled:
        tools += FILE_TOOL_NAMES
        for t in DESTRUCTIVE_FILE_TOOLS:
            if t not in hitl:
                hitl.append(t)
    tools += _COORDINATOR_TOOLS if is_coordinator else _MEMBER_TOOLS

    config = AgentConfig(
        agent_id=agent.id,
        org_id=org_id,
        name=agent.name,
        system_prompt=system_prompt,
        provider=agent.provider,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        max_steps=agent.max_steps,
        timeout_seconds=agent.timeout_seconds,
        tool_names=tools,
        hitl_tool_names=[],  # ekip çalıştırmasında HITL devre dışı (otomatik akış)
    )

    provider = await get_provider_for_agent(db, agent)

    from app.services.mcp.resolver import resolve_agent_mcp_tools
    mcp_tools = await resolve_agent_mcp_tools(db, agent)

    tracer = Tracer(
        redis=redis,
        organization_id=str(org_id),
        name=f"team:{ROLE_LABELS.get(member.role, member.role)}",
        parent_trace_id=parent_trace_id,
    )
    tool_context = ToolContext(
        org_id=org_id,
        trace_id=tracer.trace_id,
        db=db,
        redis=redis,
        agent_id=agent.id,
        team_id=team_id,
        team_run_id=team_run_id,
        current_role=member.role,
    )
    return AgentRunner(
        config=config,
        provider=provider,
        tracer=tracer,
        tool_context=tool_context,
        mcp_tools=mcp_tools,
    )
