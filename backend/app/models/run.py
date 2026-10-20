from __future__ import annotations
from uuid import uuid4
from datetime import datetime

from sqlalchemy import String, Text, JSON, ForeignKey, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin
from app.enums import ExecutionStatus, EvaluatorStatus, RunMode


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    integration_id: Mapped[str] = mapped_column(String(36), ForeignKey("integrations.id"), nullable=False)
    dataset_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mode: Mapped[RunMode] = mapped_column(String(30), default=RunMode.FULL_DATASET, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    """running | completed | cancelled"""

    baseline_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("runs.id"), nullable=True)
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    executions: Mapped[list["TestExecution"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class TestExecution(Base, TimestampMixin):
    __test__ = False  # not a pytest test class -- this is a TrustTrace domain model
    __tablename__ = "test_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_cases.id"), nullable=False)

    actual_input: Mapped[dict] = mapped_column(JSON, default=dict)
    actual_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        String(20), default=ExecutionStatus.PENDING, nullable=False
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    config_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    """Whatever app/model/prompt config metadata the adapter made available."""

    retrieved_passages: Mapped[list] = mapped_column(JSON, default=list)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)

    error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Safe, redacted error message -- never a raw stack trace shown to ordinary users."""

    run: Mapped[Run] = relationship(back_populates="executions")
    trace_events: Mapped[list["TraceEvent"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan", order_by="TraceEvent.sequence_index"
    )
    evaluator_results: Mapped[list["EvaluatorResult"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )


class TraceEvent(Base, TimestampMixin):
    """
    One stage of execution (e.g. "retrieve", "extract", "review"). Stage
    names are adapter/target-defined, not a fixed core enum, because
    different target applications have different pipelines.
    """

    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_executions.id"), nullable=False
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    """ok | unavailable | error"""
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    execution: Mapped[TestExecution] = relationship(back_populates="trace_events")


class EvaluatorResult(Base, TimestampMixin):
    __tablename__ = "evaluator_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_executions.id"), nullable=False
    )
    evaluator_name: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    status: Mapped[EvaluatorStatus] = mapped_column(String(20), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actual_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """Only set when status == fail; carried from the test case's severity."""

    execution: Mapped[TestExecution] = relationship(back_populates="evaluator_results")
