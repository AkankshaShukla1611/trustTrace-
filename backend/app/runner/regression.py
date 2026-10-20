from __future__ import annotations

from sqlalchemy.orm import Session

from app.enums import ExecutionStatus
from app.models.run import Run, TestExecution
from app.models.test_case import TestCase


def _executions_by_test_case(db: Session, run_id: str) -> dict[str, TestExecution]:
    executions = db.query(TestExecution).filter(TestExecution.run_id == run_id).all()
    return {e.test_case_id: e for e in executions}


def compare_runs(db: Session, baseline_run_id: str, candidate_run_id: str) -> dict:
    """
    Compares two saved runs test-case by test-case. Only test cases present
    in both runs are comparable; everything else is reported explicitly
    as non-comparable rather than silently dropped.
    """
    baseline_run = db.get(Run, baseline_run_id)
    candidate_run = db.get(Run, candidate_run_id)
    if baseline_run is None or candidate_run is None:
        raise ValueError("baseline or candidate run not found")

    baseline = _executions_by_test_case(db, baseline_run_id)
    candidate = _executions_by_test_case(db, candidate_run_id)

    all_ids = set(baseline) | set(candidate)
    comparable_ids = set(baseline) & set(candidate)
    non_comparable = sorted(all_ids - comparable_ids)

    new_failures, resolved_failures, unchanged_failures, newly_passed = [], [], [], []
    category_changes: dict[str, dict[str, int]] = {}
    critical_failures = []

    test_cases = {tc.id: tc for tc in db.query(TestCase).filter(TestCase.id.in_(comparable_ids)).all()}

    for test_case_id in sorted(comparable_ids):
        base_status = baseline[test_case_id].status
        cand_status = candidate[test_case_id].status
        test_case = test_cases.get(test_case_id)
        category = test_case.category if test_case else "unknown"

        bucket = category_changes.setdefault(category, {"improved": 0, "regressed": 0, "unchanged": 0})

        if base_status == ExecutionStatus.FAILED and cand_status == ExecutionStatus.PASSED:
            resolved_failures.append(test_case_id)
            bucket["improved"] += 1
        elif base_status in (ExecutionStatus.PASSED, ExecutionStatus.UNEVALUATED) and cand_status == ExecutionStatus.FAILED:
            new_failures.append(test_case_id)
            bucket["regressed"] += 1
            if test_case and test_case.severity == "critical":
                critical_failures.append(test_case_id)
        elif base_status == ExecutionStatus.FAILED and cand_status == ExecutionStatus.FAILED:
            unchanged_failures.append(test_case_id)
            bucket["unchanged"] += 1
        elif base_status in (ExecutionStatus.UNEVALUATED, ExecutionStatus.EXECUTION_ERROR) and cand_status == ExecutionStatus.PASSED:
            newly_passed.append(test_case_id)
            bucket["improved"] += 1
        else:
            bucket["unchanged"] += 1

    return {
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "new_failures": new_failures,
        "resolved_failures": resolved_failures,
        "unchanged_failures": unchanged_failures,
        "newly_passed": newly_passed,
        "non_comparable": non_comparable,
        "critical_failures": critical_failures,
        "category_changes": category_changes,
        "config_changed": baseline_run.config_snapshot != candidate_run.config_snapshot,
    }


def evaluate_release_gate(summary: dict, rules: dict) -> dict:
    """
    Configurable release-gate check over a regression summary. A critical
    failure must never be hidden by an average score -- `block_on_critical`
    defaults on.

    rules example: {"block_on_critical": True, "max_new_failures": 0}
    """
    block_on_critical = rules.get("block_on_critical", True)
    max_new_failures = rules.get("max_new_failures")

    reasons = []
    passed = True

    if block_on_critical and summary["critical_failures"]:
        passed = False
        reasons.append(f"{len(summary['critical_failures'])} critical failure(s): {summary['critical_failures']}")

    if max_new_failures is not None and len(summary["new_failures"]) > max_new_failures:
        passed = False
        reasons.append(
            f"{len(summary['new_failures'])} new failure(s) exceeds allowed maximum of {max_new_failures}"
        )

    return {"passed": passed, "reasons": reasons}
