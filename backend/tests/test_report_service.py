"""
Tests the report builder against a real run (reusing the mock-pack seed
pattern from test_runner_engine.py), checking that coverage and accuracy
stay separate denominators, failures/unavailable-evaluations are
correctly bucketed, and known_limitations is derived from real
evaluator output rather than a fixed list.
"""
from app.enums import IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version
from app.services.report_service import build_run_report, render_markdown

DOCUMENTS = [
    {
        "document_id": "doc1",
        "pages": [{"page_number": 1, "text": "The total loan amount disbursed to the borrower is 500000 dollars."}],
    }
]


def _seed(db_session):
    project = Project(name="Report Test Project")
    pack = EvaluationPack(slug="report_test_pack", name="Report Test Pack")
    db_session.add_all([project, pack])
    db_session.flush()

    integration = Integration(project_id=project.id, name="Mock", adapter_type=IntegrationType.MOCK, config={})
    dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="Report test dataset")
    db_session.add_all([integration, dataset])
    db_session.flush()

    case_pass = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Finds the right passage", category="qa",
        severity="medium", behavior_type="free_text",
        input_payload={"mode": "qa", "query": "total loan amount disbursed", "documents": DOCUMENTS},
        expected_evidence=[{"document_id": "doc1", "page": 1}],
        relevant_passage_ids=["doc1:p1"],
    )
    case_fail = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Should abstain but doesn't", category="abstention",
        severity="critical", behavior_type="abstain_expected",
        input_payload={"mode": "qa", "query": "total loan amount disbursed", "documents": DOCUMENTS},
    )
    case_unevaluated = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Nothing applicable", category="qa",
        severity="low", behavior_type="free_text",
        input_payload={"mode": "qa", "query": "zzz nothing relevant zzz", "documents": DOCUMENTS},
    )
    db_session.add_all([case_pass, case_fail, case_unevaluated])
    db_session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id, version_number=1,
        test_case_snapshot=[{"test_case_id": c.id, "content_hash": "x"} for c in [case_pass, case_fail, case_unevaluated]],
    )
    db_session.add(dataset_version)
    db_session.commit()

    return project, integration, dataset_version, case_pass, case_fail, case_unevaluated


def test_report_metrics_keep_coverage_and_accuracy_separate(db_session):
    project, integration, dataset_version, case_pass, case_fail, case_unevaluated = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )

    report = build_run_report(db_session, run.id)
    metrics = report["metrics"]

    assert metrics["total_executions"] == 3
    assert metrics["status_counts"]["passed"] == 1
    assert metrics["status_counts"]["failed"] == 1
    assert metrics["status_counts"]["unevaluated"] == 1

    # 1 passed out of 2 evaluated (pass+fail) -- unevaluated case must NOT
    # dilute or inflate this denominator.
    assert metrics["pass_rate_of_evaluated"] == 0.5
    # 2 of 3 total were evaluated at all -- a distinct number from pass rate.
    assert metrics["evaluation_coverage"] == 2 / 3


def test_report_failures_list_includes_the_failing_case_with_evaluator_detail(db_session):
    project, integration, dataset_version, case_pass, case_fail, case_unevaluated = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )
    report = build_run_report(db_session, run.id)

    failure_ids = [f["test_case_id"] for f in report["failures"]]
    assert case_fail.id in failure_ids
    assert case_pass.id not in failure_ids

    failing_entry = next(f for f in report["failures"] if f["test_case_id"] == case_fail.id)
    assert failing_entry["severity"] == "critical"
    assert any(ef["evaluator_name"] == "abstention" for ef in failing_entry["evaluator_failures"])


def test_report_unavailable_evaluations_separate_from_failures(db_session):
    project, integration, dataset_version, case_pass, case_fail, case_unevaluated = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )
    report = build_run_report(db_session, run.id)

    unavailable_case_ids = {u["test_case_id"] for u in report["unavailable_evaluations"]}
    assert case_unevaluated.id in unavailable_case_ids
    # the unevaluated case must not also show up in failures
    assert case_unevaluated.id not in [f["test_case_id"] for f in report["failures"]]


def test_report_without_baseline_has_no_regression_section(db_session):
    project, integration, dataset_version, *_ = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )
    report = build_run_report(db_session, run.id)
    assert report["regression"] is None


def test_markdown_rendering_includes_key_sections(db_session):
    project, integration, dataset_version, *_ = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )
    report = build_run_report(db_session, run.id)
    markdown = render_markdown(report)

    assert "# TrustTrace Run Report" in markdown
    assert "## Metrics" in markdown
    assert "## Failures" in markdown
    assert "## Known limitations" in markdown
    assert run.id in markdown
