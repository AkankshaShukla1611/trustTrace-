from datetime import datetime, timezone

from app.enums import ExecutionStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.run import Run, TestExecution
from app.models.test_case import TestCase
from app.runner.regression import compare_runs, evaluate_release_gate


def _seed_runs(db_session):
    project = Project(name="Regression Demo")
    pack = EvaluationPack(slug="mock_pack2", name="Mock Pack 2")
    db_session.add_all([project, pack])
    db_session.flush()

    integration = Integration(project_id=project.id, name="Mock", adapter_type=IntegrationType.MOCK, config={})
    dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="Regression dataset")
    db_session.add_all([integration, dataset])
    db_session.flush()

    case_regressed = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Regresses", category="extraction",
        severity="critical", behavior_type="free_text", input_payload={},
    )
    case_fixed = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Gets fixed", category="citation",
        severity="medium", behavior_type="free_text", input_payload={},
    )
    case_stable_fail = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Still failing", category="extraction",
        severity="low", behavior_type="free_text", input_payload={},
    )
    db_session.add_all([case_regressed, case_fixed, case_stable_fail])
    db_session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id, version_number=1,
        test_case_snapshot=[{"test_case_id": c.id, "content_hash": "x"} for c in [case_regressed, case_fixed, case_stable_fail]],
    )
    db_session.add(dataset_version)
    db_session.flush()

    now = datetime.now(timezone.utc)
    baseline_run = Run(
        project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id,
        status="completed", started_at=now, finished_at=now, config_snapshot={"v": 1},
    )
    candidate_run = Run(
        project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id,
        status="completed", started_at=now, finished_at=now, config_snapshot={"v": 2},
    )
    db_session.add_all([baseline_run, candidate_run])
    db_session.flush()

    db_session.add_all([
        TestExecution(run_id=baseline_run.id, test_case_id=case_regressed.id, actual_input={}, status=ExecutionStatus.PASSED),
        TestExecution(run_id=candidate_run.id, test_case_id=case_regressed.id, actual_input={}, status=ExecutionStatus.FAILED),

        TestExecution(run_id=baseline_run.id, test_case_id=case_fixed.id, actual_input={}, status=ExecutionStatus.FAILED),
        TestExecution(run_id=candidate_run.id, test_case_id=case_fixed.id, actual_input={}, status=ExecutionStatus.PASSED),

        TestExecution(run_id=baseline_run.id, test_case_id=case_stable_fail.id, actual_input={}, status=ExecutionStatus.FAILED),
        TestExecution(run_id=candidate_run.id, test_case_id=case_stable_fail.id, actual_input={}, status=ExecutionStatus.FAILED),
    ])
    db_session.commit()

    return baseline_run, candidate_run, case_regressed, case_fixed, case_stable_fail


def test_compare_runs_categorizes_changes_correctly(db_session):
    baseline_run, candidate_run, case_regressed, case_fixed, case_stable_fail = _seed_runs(db_session)
    summary = compare_runs(db_session, baseline_run.id, candidate_run.id)

    assert summary["new_failures"] == [case_regressed.id]
    assert summary["resolved_failures"] == [case_fixed.id]
    assert summary["unchanged_failures"] == [case_stable_fail.id]
    # case_regressed is severity=critical and newly failing -> must surface as critical
    assert summary["critical_failures"] == [case_regressed.id]
    assert summary["non_comparable"] == []


def test_release_gate_blocks_on_critical_failure_even_with_good_average(db_session):
    baseline_run, candidate_run, *_ = _seed_runs(db_session)
    summary = compare_runs(db_session, baseline_run.id, candidate_run.id)

    # 2 of 3 test cases improved/stable, only 1 regressed -- a naive average
    # score would look fine, but the regression is a critical severity case.
    gate = evaluate_release_gate(summary, {"block_on_critical": True})
    assert gate["passed"] is False
    assert any("critical" in reason for reason in gate["reasons"])


def test_release_gate_passes_when_no_critical_and_within_budget(db_session):
    summary = {
        "new_failures": ["a"], "resolved_failures": [], "unchanged_failures": [],
        "newly_passed": [], "non_comparable": [], "critical_failures": [], "category_changes": {},
    }
    gate = evaluate_release_gate(summary, {"block_on_critical": True, "max_new_failures": 1})
    assert gate["passed"] is True
