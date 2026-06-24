"""
Prompt versiyonlama yardımcıları — loop it.6

snapshot_agent: agent'ın MEVCUT config'ini, mevcut prompt_version numarasıyla bir
AgentPromptVersion satırı olarak kaydeder. agent her config değişiminde çağrılır.
config_changed: bir update'in versiyonlanan alanlardan birini değiştirip değiştirmediği.
"""
from __future__ import annotations

import uuid

from app.models.agent import Agent
from app.models.agent_prompt_version import VERSIONED_FIELDS, AgentPromptVersion


def config_dict(agent: Agent) -> dict:
    """Versiyonlanan config alanlarının anlık görüntüsü (karşılaştırma için)."""
    return {f: list(getattr(agent, f) or []) if f.endswith("_names") else getattr(agent, f) for f in VERSIONED_FIELDS}


def snapshot_agent(db, agent: Agent, *, note: str | None = None, created_by: uuid.UUID | None = None) -> AgentPromptVersion:
    """Agent'ın mevcut config'ini mevcut prompt_version ile satır olarak ekler (commit ÇAĞIRMAZ)."""
    row = AgentPromptVersion(
        id=uuid.uuid4(),
        agent_id=agent.id,
        version=agent.prompt_version,
        system_prompt=agent.system_prompt,
        provider=agent.provider,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        tool_names=list(agent.tool_names or []),
        hitl_tool_names=list(agent.hitl_tool_names or []),
        note=note,
        created_by=created_by,
    )
    db.add(row)
    return row
