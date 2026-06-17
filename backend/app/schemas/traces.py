"""Trace Pydantic Schemas (M8)."""
from typing import Any

from pydantic import BaseModel


class TestCompletionRequest(BaseModel):
    model: str
    prompt: str
    system: str | None = None


class TraceSummary(BaseModel):
    trace_id: str
    name: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None


class TraceEvent(BaseModel):
    type: str
    payload: dict[str, Any]
    timestamp: str | None = None


class TraceDetail(TraceSummary):
    events: list[TraceEvent] = []
