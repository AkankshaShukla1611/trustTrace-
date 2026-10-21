"""
Runs a real test case through the real runner with the LLM judge
opted in and the Anthropic client mocked (no real key/network needed),
proving the whole path wires together: runner -> ALL_EVALUATORS ->
llm_judge -> NEEDS_REVIEW rollup -> persisted EvaluatorResult row.
"""
import json

from app.enums import ExecutionStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, content):
        self.content = content


def _fake_anthropic_client(verdict: str, reasoning: str):
    class FakeMessages:
        def create(self, **kwargs):
            return _FakeResponse([_FakeTextBlock(json.dumps({"verdict": verdict, "reasoning": reasoning}))])

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = FakeMessages()

    return FakeClient


def _seed(db_session):
    project = Project(name="LLM judge e2e test")
    pack = EvaluationPack(slug="llm_judge_e2e_pack", name="LLM judge e2e pack")
    db_session.add_all([project, pack])
    db_session.flush()

    integration = Integration(project_id=project.id, name="Mock", adapter_type=IntegrationType.MOCK, config={})
    dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="ds")
    db_session.add_all([integration, dataset])
    db_session.flush()

    case = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Judged free-text answer",
        category="qa", severity="medium", behavior_type="free_text",
        input_payload={"mode": "qa", "query": "irrelevant for this mocked adapter", "documents": []},
        evaluator_config={"llm_judge": {}},
    )
    db_session.add(case)
    db_session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id, version_number=1,
        test_case_snapshot=[{"test_case_id": case.id, "content_hash": "x"}],
    )
    db_session.add(dataset_version)
    db_session.commit()
    return project, integration, dataset_version, case


def test_runner_persists_a_real_pass_verdict_from_the_judge(db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr("anthropic.Anthropic", _fake_anthropic_client("pass", "Correctly abstained, as expected."))

    project, integration, dataset_version, case = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )

    execution = run.executions[0]
    assert execution.status == ExecutionStatus.PASSED
    judge_result = next(r for r in execution.evaluator_results if r.evaluator_name == "llm_judge")
    assert judge_result.status == "pass"
    assert judge_result.reason == "Correctly abstained, as expected."


def test_runner_marks_needs_review_on_inconclusive_verdict(db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(
        "anthropic.Anthropic", _fake_anthropic_client("inconclusive", "Can't tell if this satisfies the criteria.")
    )

    project, integration, dataset_version, case = _seed(db_session)
    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )

    execution = run.executions[0]
    assert execution.status == ExecutionStatus.NEEDS_REVIEW
