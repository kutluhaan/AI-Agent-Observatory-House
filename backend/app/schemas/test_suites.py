"""
Pydantic schemas — Test Suite CRUD ve run endpoint'leri (M11).
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field


# ─── TestSuite ────────────────────────────────────────────

class CreateTestSuiteRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    config_yaml: Annotated[str, Field(min_length=1)]


class UpdateTestSuiteRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    config_yaml: Annotated[str, Field(min_length=1)] | None = None


class TestSuiteResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    config_yaml: str
    created_by: uuid.UUID | None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "TestSuiteResponse":
        return cls(
            id=obj.id,
            name=obj.name,
            description=obj.description,
            config_yaml=obj.config_yaml,
            created_by=obj.created_by,
            created_at=obj.created_at.isoformat(),
            updated_at=obj.updated_at.isoformat(),
        )


# ─── TestRun ──────────────────────────────────────────────

class RunTestSuiteRequest(BaseModel):
    parallel: bool = False


class TestRunResponse(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    status: str
    parallel: bool
    started_at: str | None
    ended_at: str | None
    summary: dict[str, Any] | None
    created_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "TestRunResponse":
        return cls(
            id=obj.id,
            suite_id=obj.suite_id,
            status=obj.status,
            parallel=obj.parallel,
            started_at=obj.started_at.isoformat() if obj.started_at else None,
            ended_at=obj.ended_at.isoformat() if obj.ended_at else None,
            summary=obj.summary,
            created_at=obj.created_at.isoformat(),
        )


# ─── TestCaseResult ───────────────────────────────────────

class TestCaseResultResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    status: str
    output: str | None
    trace_id: str | None
    latency_ms: int | None
    steps_taken: int | None
    total_tokens: int | None
    assertions_results: list[dict[str, Any]]
    rag_metrics: dict[str, Any] | None
    trajectory: list[dict[str, Any]] | None
    cost_usd: float | None
    error_message: str | None
    created_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> "TestCaseResultResponse":
        return cls(
            id=obj.id,
            case_id=obj.case_id,
            status=obj.status,
            output=obj.output,
            trace_id=obj.trace_id,
            latency_ms=obj.latency_ms,
            steps_taken=obj.steps_taken,
            total_tokens=obj.total_tokens,
            assertions_results=obj.assertions_results or [],
            rag_metrics=obj.rag_metrics,
            trajectory=obj.trajectory,
            cost_usd=obj.cost_usd,
            error_message=obj.error_message,
            created_at=obj.created_at.isoformat(),
        )


# ─── TestRun Detail (run + case results) ──────────────────

class TestRunDetailResponse(BaseModel):
    run: TestRunResponse
    case_results: list[TestCaseResultResponse]
