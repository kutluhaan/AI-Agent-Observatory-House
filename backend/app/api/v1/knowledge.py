"""
Agent Knowledge Router — Faz 4

  GET    /agents/{agent_id}/knowledge          — bilgi öğelerini listele (member)
  POST   /agents/{agent_id}/knowledge          — öğe ekle (admin)
  PATCH  /agents/{agent_id}/knowledge/{kid}    — öğe güncelle (admin)
  DELETE /agents/{agent_id}/knowledge/{kid}    — öğe sil (admin)

constitution/rule/instruction/prompt → her zaman aktif (system prompt).
skill → talep üzerine (list_skills/read_skill tool'ları).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_role
from app.api.v1.agents import _get_agent_or_404
from app.core.database import get_db
from app.core.responses import NotFoundError, success
from app.models.agent_knowledge import AgentKnowledge
from app.schemas.knowledge import (
    CreateKnowledgeRequest,
    KnowledgeResponse,
    UpdateKnowledgeRequest,
)
from app.services.agent import knowledge_store

router = APIRouter()


async def _get_item_or_404(
    kid: uuid.UUID, agent_id: uuid.UUID, db: AsyncSession
) -> AgentKnowledge:
    res = await db.execute(
        select(AgentKnowledge).where(
            AgentKnowledge.id == kid,
            AgentKnowledge.agent_id == agent_id,
        )
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise NotFoundError("KNOWLEDGE_NOT_FOUND", "Knowledge item not found.")
    return item


@router.get("/{agent_id}/knowledge")
async def list_knowledge(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("member")),
):
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    items = await knowledge_store.list_all(db, agent_id)
    return success([KnowledgeResponse.from_orm(i).model_dump() for i in items])


@router.post("/{agent_id}/knowledge", status_code=201)
async def create_knowledge(
    agent_id: uuid.UUID,
    body: CreateKnowledgeRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    agent = await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    item = AgentKnowledge(
        agent_id=agent.id,
        organization_id=ctx.org_id,
        kind=body.kind,
        name=body.name,
        content=body.content,
        is_active=True,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return success(KnowledgeResponse.from_orm(item).model_dump())


@router.patch("/{agent_id}/knowledge/{kid}")
async def update_knowledge(
    agent_id: uuid.UUID,
    kid: uuid.UUID,
    body: UpdateKnowledgeRequest,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    item = await _get_item_or_404(kid, agent_id, db)
    for field_name, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, field_name, value)
    await db.commit()
    await db.refresh(item)
    return success(KnowledgeResponse.from_orm(item).model_dump())


@router.delete("/{agent_id}/knowledge/{kid}", status_code=204)
async def delete_knowledge(
    agent_id: uuid.UUID,
    kid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require_role("admin")),
):
    await _get_agent_or_404(agent_id, ctx.org_id, db)  # type: ignore[arg-type]
    item = await _get_item_or_404(kid, agent_id, db)
    await db.delete(item)
    await db.commit()
