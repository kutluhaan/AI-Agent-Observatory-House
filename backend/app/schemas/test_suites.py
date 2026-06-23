"""
Pydantic schemas — Test Suite CRUD ve run endpoint'leri (M11).
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from app.services.test_suite.kpi_catalog import VALID_KPI_KEYS


def _validate_kpis(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    invalid = [k for k in v if k not in VALID_KPI_KEYS]
    if invalid:
        raise ValueError(f"Unknown KPI key(s): {', '.join(invalid)}")
    return v


# ─── TestSuite ────────────────────────────────────────────

class CreateTestSuiteRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    config_yaml: Annotated[str, Field(min_length=1)]
    kpis: list[str] | None = None

    _check_kpis = field_validator("kpis")(_validate_kpis)


class CreateSuiteFromDatasetRequest(BaseModel):
    """B2: CSV/JSONL dataset'ten suite oluştur."""
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: str | None = None
    agent_id: uuid.UUID
    format: str  # csv | jsonl
    content: Annotated[str, Field(min_length=1)]
    assertion: str = "contains"  # contains | equals | regex


class UpdateTestSuiteRequest(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    config_yaml: Annotated[str, Field(min_length=1)] | None = None
    kpis: list[str] | None = None

    _check_kpis = field_validator("kpis")(_validate_kpis)


class TestSuiteResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    config_yaml: str
    kpis: list[str] | None
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
            kpis=obj.kpis,
            created_by=obj.created_by,
            created_at=obj.created_at.isoformat(),
            updated_at=obj.updated_at.isoformat(),
        )


# ─── TestRun ──────────────────────────────────────────────

class RunTestSuiteRequest(BaseModel):
    parallel: bool = False


class PromptVariant(BaseModel):
    label: Annotated[str, Field(min_length=1, max_length=120)]
    system_prompt: Annotated[str, Field(min_length=1)]


class RunExperimentRequest(BaseModel):
    """F4.3 A/B: aynı suite'i farklı system prompt'larla yan yana çalıştır."""
    parallel: bool = False
    variants: Annotated[list[PromptVariant], Field(min_length=2, max_length=5)]

    @field_validator("variants")
    @classmethod
    def _unique_labels(cls, v: list[PromptVariant]) -> list[PromptVariant]:
        labels = [x.label for x in v]
        if len(set(labels)) != len(labels):
            raise ValueError("Variant labels must be unique.")
        return v


class TestRunResponse(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    status: str
    parallel: bool
    started_at: str | None
    ended_at: str | None
    summary: dict[str, Any] | None
    experiment_id: uuid.UUID | None
    variant_label: str | None
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
            experiment_id=getattr(obj, "experiment_id", None),
            variant_label=getattr(obj, "variant_label", None),
            created_at=obj.created_at.isoformat(),
        )


class ExperimentVariantResult(BaseModel):
    run_id: uuid.UUID
    variant_label: str | None
    status: str
    summary: dict[str, Any] | None
    system_prompt_override: str | None


class ExperimentResponse(BaseModel):
    experiment_id: uuid.UUID
    suite_id: uuid.UUID
    created_at: str
    status: str  # running | completed (tüm varyantlar bitti)
    variants: list[ExperimentVariantResult]


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
    judge_results: list[dict[str, Any]] | None
    consistency: dict[str, Any] | None
    steps_results: list[dict[str, Any]] | None
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
            judge_results=obj.judge_results,
            consistency=obj.consistency,
            steps_results=getattr(obj, "steps_results", None),
            cost_usd=obj.cost_usd,
            error_message=obj.error_message,
            created_at=obj.created_at.isoformat(),
        )


# ─── TestRun Detail (run + case results) ──────────────────

class TestRunDetailResponse(BaseModel):
    run: TestRunResponse
    case_results: list[TestCaseResultResponse]
