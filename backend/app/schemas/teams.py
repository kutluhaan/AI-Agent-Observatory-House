"""Pydantic schemas — Agent ekipleri (F8)."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator

from app.services.team.roles import COORDINATOR


class TeamMemberInput(BaseModel):
    agent_id: uuid.UUID
    role: Annotated[str, Field(min_length=1, max_length=50)]
    role_prompt: str = ""
    position: int = 0


class CreateTeamRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    members: Annotated[list[TeamMemberInput], Field(min_length=1)]

    @model_validator(mode="after")
    def _require_coordinator(self):
        roles = [m.role for m in self.members]
        if roles.count(COORDINATOR) != 1:
            raise ValueError("Team must have exactly one 'coordinator' member.")
        return self


class UpdateTeamRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    members: list[TeamMemberInput] | None = None

    @model_validator(mode="after")
    def _coordinator_if_members(self):
        if self.members is not None and [m.role for m in self.members].count(COORDINATOR) != 1:
            raise ValueError("Team must have exactly one 'coordinator' member.")
        return self


class TeamMemberResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str | None
    role: str
    role_prompt: str
    position: int

    @classmethod
    def from_orm(cls, m: Any) -> "TeamMemberResponse":
        return cls(
            id=m.id, agent_id=m.agent_id,
            agent_name=m.agent.name if getattr(m, "agent", None) else None,
            role=m.role, role_prompt=m.role_prompt or "", position=m.position,
        )


class TeamResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    members: list[TeamMemberResponse]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, t: Any) -> "TeamResponse":
        return cls(
            id=t.id, name=t.name, description=t.description,
            members=[TeamMemberResponse.from_orm(m) for m in t.members],
            created_at=t.created_at.isoformat(), updated_at=t.updated_at.isoformat(),
        )


class RunTeamRequest(BaseModel):
    input: Annotated[str, Field(min_length=1)]
    conversation_id: uuid.UUID | None = None  # B3: çok-turlu sohbet (yoksa yeni sohbet)


class TeamRunResponse(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    status: str
    input: str
    final_output: str | None
    error_message: str | None
    conversation_id: uuid.UUID | None
    started_at: str | None
    ended_at: str | None
    created_at: str

    @classmethod
    def from_orm(cls, r: Any) -> "TeamRunResponse":
        return cls(
            id=r.id, team_id=r.team_id, status=r.status, input=r.input,
            final_output=r.final_output, error_message=r.error_message,
            conversation_id=getattr(r, "conversation_id", None),
            started_at=r.started_at.isoformat() if r.started_at else None,
            ended_at=r.ended_at.isoformat() if r.ended_at else None,
            created_at=r.created_at.isoformat(),
        )


class TeamConversation(BaseModel):
    conversation_id: uuid.UUID
    first_input: str
    turns: int
    last_status: str
    created_at: str
    updated_at: str


class TeamRunMessageResponse(BaseModel):
    id: uuid.UUID
    kind: str
    from_role: str | None
    to_role: str | None
    title: str | None
    content: str
    created_at: str

    @classmethod
    def from_orm(cls, m: Any) -> "TeamRunMessageResponse":
        return cls(
            id=m.id, kind=m.kind, from_role=m.from_role, to_role=m.to_role,
            title=m.title, content=m.content, created_at=m.created_at.isoformat(),
        )


class TeamRunDetailResponse(BaseModel):
    run: TeamRunResponse
    messages: list[TeamRunMessageResponse]
