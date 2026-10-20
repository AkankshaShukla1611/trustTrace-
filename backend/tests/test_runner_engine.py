from app.enums import ExecutionStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.document import DocumentFixture
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.run import TestExecution
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version

DOCUMENTS = [
    {
        "document_id": "loan_agreement",
        "pages": [{"page_number": 1, "text": "The total loan amount disbursed to the borrower is 500000 dollars."}],
    }
]


def _seed(db_session):
    project = Project(name="Mock Demo Project")
    pack = EvaluationPack(slug="mock_pack", name="Mock Evaluation Pack", rules_config={})
    db_session.add_all([project, pack])
    db_session.flush()

    integration = Integration(project_id=project.id, name="Mock Adapter", adapter_type=IntegrationType.MOCK, config={})
    doc = DocumentFixture(
        id="loan_agreement",
        project_id=project.id,
        filename="loan_agreement.txt",
        doc_type="synthetic",
        pages=DOCUMENTS[0]["pages"],
    )
    dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="Mock dataset")
    db_session.add_all([integration, doc, dataset])
    db_session.flush()

    cases = {
        "case_pass_citation": TestCase(
            dataset_id=dataset.id,
            evaluation_pack_id=pack.id,
            name="Finds answer with grounded citation",
            category="qa",
            severity="medium",
            behavior_type="free_text",
            input_payload={"mode": "qa", "query": "total loan amount disbursed", "documents": DOCUMENTS},
            expected_evidence=[{"document_id": "loan_agreement", "page": 1}],
            relevant_passage_ids=["loan_agreement:p1"],
        ),
        "case_pass_abstain": TestCase(
            dataset_id=dataset.id,
            evaluation_pack_id=pack.id,
            name="Correctly abstains on unanswerable question",
            category="abstention",
            severity="high",
            behavior_type="abstain_expected",
            input_payload={"mode": "qa", "query": "quantum entanglement physics", "documents": DOCUMENTS},
        ),
        "case_fail_abstain": TestCase(
            dataset_id=dataset.id,
            evaluation_pack_id=pack.id,
            name="Should abstain but finds an answer instead",
            category="abstention",
            severity="critical",
            behavior_type="abstain_expected",
            # deliberately a query that WILL match -> abstention evaluator should fail this
            input_payload={"mode": "qa", "query": "total loan amount disbursed", "documents": DOCUMENTS},
        ),
        "case_unevaluated": TestCase(
            dataset_id=dataset.id,
            evaluation_pack_id=pack.id,
            name="No applicable evaluator configured",
            category="qa",
            severity="low",
            behavior_type="free_text",
            input_payload={"mode": "qa", "query": "something with zero relevant passages xyz", "documents": DOCUMENTS},
        ),
        "case_execution_error": TestCase(
            dataset_id=dataset.id,
            evaluation_pack_id=pack.id,
            name="Adapter error",
            category="reliability",
            severity="medium",
            behavior_type="free_text",
            input_payload={"mode": "simulate_error"},
        ),
    }
    db_session.add_all(cases.values())
    db_session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=1,
        test_case_snapshot=[{"test_case_id": tc.id, "content_hash": "x"} for tc in cases.values()],
    )
    db_session.add(dataset_version)
    db_session.flush()

    return project, integration, dataset_version, cases


def test_full_run_persists_distinct_statuses_per_case(db_session):
    project, integration, dataset_version, cases = _seed(db_session)

    run = run_dataset_version(
        db_session,
        project_id=project.id,
        integration_id=integration.id,
        dataset_version_id=dataset_version.id,
    )

    assert run.status == "completed"
    assert run.finished_at is not None

    executions = {e.test_case_id: e for e in db_session.query(TestExecution).filter(TestExecution.run_id == run.id).all()}
    assert len(executions) == 5

    assert executions[cases["case_pass_citation"].id].status == ExecutionStatus.PASSED
    assert executions[cases["case_pass_abstain"].id].status == ExecutionStatus.PASSED
    assert executions[cases["case_fail_abstain"].id].status == ExecutionStatus.FAILED
    assert executions[cases["case_unevaluated"].id].status == ExecutionStatus.UNEVALUATED
    assert executions[cases["case_execution_error"].id].status == ExecutionStatus.EXECUTION_ERROR
    assert executions[cases["case_execution_error"].id].error_category == "adapter_error"

    # trace events were genuinely captured for the QA cases, not fabricated
    pass_exec = executions[cases["case_pass_citation"].id]
    stage_names = [t.stage_name for t in pass_exec.trace_events]
    assert stage_names == ["search", "answer"]


def test_evaluator_results_distinguish_unevaluated_from_passed(db_session):
    project, integration, dataset_version, cases = _seed(db_session)
    run = run_dataset_version(
        db_session,
        project_id=project.id,
        integration_id=integration.id,
        dataset_version_id=dataset_version.id,
    )
    unevaluated_execution = (
        db_session.query(TestExecution)
        .filter(TestExecution.run_id == run.id, TestExecution.test_case_id == cases["case_unevaluated"].id)
        .one()
    )
    statuses = {r.evaluator_name: r.status for r in unevaluated_execution.evaluator_results}
    assert all(status == "unavailable" for status in statuses.values())
