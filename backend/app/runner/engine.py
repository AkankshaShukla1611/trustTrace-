from __future__ import annotations
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.adapters import get_adapter_class
from app.adapters.base import AdapterExecutionResult
from app.enums import ExecutionStatus, RunMode
from app.evaluators import DETERMINISTIC_EVALUATORS, EvaluationContext, compute_execution_status
from app.models.document import DocumentFixture
from app.models.evaluation_pack import EvaluationPack  # noqa: F401 (keeps relationship imports resolvable)
from app.models.project import Integration
from app.models.run import EvaluatorResult, Run, TestExecution, TraceEvent
from app.models.test_case import TestCase


def _test_case_to_dict(test_case: TestCase) -> dict:
    return {
        "id": test_case.id,
        "behavior_type": test_case.behavior_type,
        "expected_output": test_case.expected_output,
        "expected_evidence": test_case.expected_evidence or [],
        "relevant_passage_ids": test_case.relevant_passage_ids or [],
        "expected_tool_calls": test_case.expected_tool_calls or [],
        "prohibited_tool_calls": test_case.prohibited_tool_calls or [],
        "evaluator_config": test_case.evaluator_config or {},
        "severity": test_case.severity,
        "category": test_case.category,
    }


def _safe_execute(adapter, input_payload: dict, timeout_seconds: float) -> AdapterExecutionResult:
    """Never let a broken/third-party adapter implementation crash the whole run."""
    try:
        return adapter.execute(input_payload, timeout_seconds=timeout_seconds)
    except Exception as exc:  # adapters wrap target-application code we don't control
        return AdapterExecutionResult(
            status="error",
            error_category="adapter_error",
            error_detail=f"adapter raised {type(exc).__name__}: {exc}",
        )


def run_dataset_version(
    db: Session,
    *,
    project_id: str,
    integration_id: str,
    dataset_version_id: str,
    mode: RunMode = RunMode.FULL_DATASET,
    test_case_ids: list[str] | None = None,
    label: str | None = None,
    baseline_run_id: str | None = None,
) -> Run:
    integration = db.get(Integration, integration_id)
    if integration is None:
        raise ValueError(f"integration {integration_id} not found")

    from app.models.dataset import DatasetVersion

    dataset_version = db.get(DatasetVersion, dataset_version_id)
    if dataset_version is None:
        raise ValueError(f"dataset version {dataset_version_id} not found")

    snapshot_ids = [entry["test_case_id"] for entry in dataset_version.test_case_snapshot]
    if mode in (RunMode.SELECTED_CASES, RunMode.SINGLE_CASE) and test_case_ids:
        snapshot_ids = [tc_id for tc_id in snapshot_ids if tc_id in test_case_ids]

    test_cases = db.query(TestCase).filter(TestCase.id.in_(snapshot_ids)).all() if snapshot_ids else []
    test_cases_by_id = {tc.id: tc for tc in test_cases}

    documents = db.query(DocumentFixture).filter(DocumentFixture.project_id == project_id).all()
    documents_by_id = {doc.id: {"pages": doc.pages} for doc in documents}

    adapter_class = get_adapter_class(integration.adapter_type)
    adapter = adapter_class(integration.config)

    run = Run(
        project_id=project_id,
        integration_id=integration_id,
        dataset_version_id=dataset_version_id,
        label=label,
        mode=mode,
        status="running",
        baseline_run_id=baseline_run_id,
        config_snapshot={"integration_config": integration.config, "adapter_type": integration.adapter_type},
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()

    for test_case_id in snapshot_ids:
        test_case = test_cases_by_id.get(test_case_id)
        if test_case is None:
            # Dataset snapshot references a test case that no longer exists.
            execution = TestExecution(
                run_id=run.id,
                test_case_id=test_case_id,
                actual_input={},
                actual_output=None,
                status=ExecutionStatus.EXECUTION_ERROR,
                error_category="config_error",
                error_detail="test case referenced by dataset snapshot no longer exists",
            )
            db.add(execution)
            continue

        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        timeout = integration.config.get("timeout_seconds", 30.0)
        result = _safe_execute(adapter, test_case.input_payload, timeout)
        duration_ms = (time.perf_counter() - start_perf) * 1000

        execution = TestExecution(
            run_id=run.id,
            test_case_id=test_case.id,
            actual_input=test_case.input_payload,
            actual_output=result.output,
            started_at=started_at,
            duration_ms=duration_ms,
            config_metadata=result.config_metadata,
            retrieved_passages=result.retrieved_passages,
            tool_calls=result.tool_calls,
            error_category=result.error_category,
            error_detail=result.error_detail,
        )
        db.add(execution)
        db.flush()

        for i, trace in enumerate(result.trace_events):
            db.add(
                TraceEvent(
                    execution_id=execution.id,
                    sequence_index=i,
                    stage_name=trace.stage_name,
                    status=trace.status,
                    payload=trace.payload,
                    occurred_at=datetime.now(timezone.utc),
                )
            )

        if result.status != "ok":
            execution.status = ExecutionStatus.EXECUTION_ERROR
            db.flush()
            continue

        ctx = EvaluationContext(
            test_case=_test_case_to_dict(test_case),
            actual_output=result.output,
            retrieved_passages=result.retrieved_passages,
            tool_calls=result.tool_calls,
            config_metadata=result.config_metadata,
            documents_by_id=documents_by_id,
        )

        outcomes = [evaluator.evaluate(ctx) for evaluator in DETERMINISTIC_EVALUATORS]
        for evaluator, outcome in zip(DETERMINISTIC_EVALUATORS, outcomes):
            db.add(
                EvaluatorResult(
                    execution_id=execution.id,
                    evaluator_name=evaluator.name,
                    evaluator_version=evaluator.version,
                    status=outcome.status,
                    score=outcome.score,
                    expected_value=outcome.expected_value,
                    actual_value=outcome.actual_value,
                    reason=outcome.reason,
                    evidence=outcome.evidence,
                    limitations=outcome.limitations,
                    severity=outcome.severity,
                )
            )

        execution.status = compute_execution_status(outcomes)
        db.flush()

    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
