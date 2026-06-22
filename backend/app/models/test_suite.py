import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.organization import Organization
    from app.models.user import User


class TestSuite(Base):
    """
    Bir org'a ait test senaryoları koleksiyonu.
    config_yaml: YAML formatında raw test tanımı (parser tarafından işlenir).
    """
    __tablename__ = "test_suites"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_suite_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    # F4.2: bu suite için izlenen KPI anahtarları; NULL → kpi_catalog.DEFAULT_KPIS
    kpis: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User | None"] = relationship("User")
    cases: Mapped[list["TestCase"]] = relationship(
        "TestCase", back_populates="suite", cascade="all, delete-orphan"
    )
    runs: Mapped[list["TestRun"]] = relationship(
        "TestRun", back_populates="suite", cascade="all, delete-orphan"
    )


class TestCase(Base):
    """
    Test suite içindeki tek bir senaryo.
    assertions: [{type, value}] listesi — AssertionEngine tarafından işlenir.
    rag_context: RAG değerlendirmesi için altın standart context chunks.
    """
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    assertions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # LLM-as-judge metrikleri (Faz B): [{type, threshold, expected?, criteria?, name?}]
    judges: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    # Tutarlılık (Faz C): case'i kaç kez çalıştır + geçmesi için min geçme oranı
    repeat: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    min_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    rag_context: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # F6: senaryo adımları [{input, assertions:[{type,value}]}]; NULL → tekil case
    steps: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    suite: Mapped["TestSuite"] = relationship("TestSuite", back_populates="cases")
    agent: Mapped["Agent | None"] = relationship("Agent")


class TestRun(Base):
    """
    Bir test suite'in tek bir çalıştırması.
    summary: {total, passed, failed, error, pass_rate, avg_latency_ms, total_tokens}
    """
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_suites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | running | completed | failed | cancelled
    parallel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # F4.3: A/B prompt deneyi — aynı experiment_id'li run'lar yan yana karşılaştırılır
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    variant_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    system_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    suite: Mapped["TestSuite"] = relationship("TestSuite", back_populates="runs")
    case_results: Mapped[list["TestCaseResult"]] = relationship(
        "TestCaseResult", back_populates="run", cascade="all, delete-orphan"
    )


class TestCaseResult(Base):
    """
    Tek bir test case'in bir run içindeki sonucu.
    assertions_results: [{type, passed, expected, actual, message}]
    rag_metrics: {faithfulness, answer_relevancy, context_recall, context_precision}
    """
    __tablename__ = "test_case_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # passed | failed | error | skipped
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps_taken: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assertions_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rag_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Adım-adım trajectory: [{name, arguments, result, ok}] — agent'ın test sırasında ne yaptığı
    trajectory: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # LLM-as-judge skorları (Faz B): [{type, score, passed, threshold, rationale|error}]
    judge_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Tutarlılık (Faz C): {runs, passed_runs, pass_rate, min_pass_rate, runs_detail}
    consistency: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # F6: senaryo adım sonuçları [{step, input, output, passed, latency_ms, assertions_results}]
    steps_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Token kullanımından yaklaşık USD maliyet
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped["TestRun"] = relationship("TestRun", back_populates="case_results")
    case: Mapped["TestCase"] = relationship("TestCase")
