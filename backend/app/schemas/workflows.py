"""Pydantic schemas — Workflow CRUD."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    graph_json: dict[str, Any] | None = None


class UpdateWorkflowRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None  # active | unavailable | completed
    graph_json: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    graph_json: dict[str, Any] | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
