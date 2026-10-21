"""
Tests the report builder's handling of NEEDS_REVIEW executions (from an
inconclusive LLM judge verdict): a dedicated needs_review bucket,
separate from failures and from the pass-rate/coverage denominators,
and present in the Markdown rendering.
"""
import json

from app.enums import ExecutionStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version
from app.services.report_service import build_run_report, render_markdown


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, content):
        self.content = content


def _fake_anthropic_client():
    class FakeMessages:
        def create(self, **kwargs):
            return _FakeResponse(
                [_FakeTextBlock(json.dumps({"verdict": "inconclusive", "reasoning": "Genuinely ambiguous."}))]
            )

    class FakeClient:
        def __init__(self, *a, **kw):
            self.messages = FakeMessages()

    return FakeClient


def test_report_puts_inconclusive_judge_result_in_needs_review_not_failures(db_session, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr("anthropic.Anthropic", _fake_anthropic_client())

    project = Project(name="Needs-review report test")
    pack = EvaluationPack(slug="needs_review_report_pack", name="pack")
    db_session.add_all([project, pack])
    db_session.flush()

    integration = Integration(project_id=project.id, name="Mock", adapter_type=IntegrationType.MOCK, config={})
    dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="ds")
    db_session.add_all([integration, dataset])
    db_session.flush()

    case = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Ambiguous free-text case",
        category="qa", severity="medium", behavior_type="free_text",
        input_payload={"mode": "qa", "query": "irrelevant", "documents": []},
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

    run = run_dataset_version(
        db_session, project_id=project.id, integration_id=integration.id, dataset_version_id=dataset_version.id
    )
    assert run.executions[0].status == ExecutionStatus.NEEDS_REVIEW

    report = build_run_report(db_session, run.id)
    assert report["metrics"]["status_counts"]["needs_review"] == 1
    assert report["failures"] == []
    assert len(report["needs_review"]) == 1
    assert report["needs_review"][0]["test_case_name"] == "Ambiguous free-text case"
    assert report["needs_review"][0]["evaluator_inconclusive"][0]["evaluator_name"] == "llm_judge"

    # needs_review must not be counted as evaluated for pass-rate/coverage purposes
    assert report["metrics"]["pass_rate_of_evaluated"] is None
    assert report["metrics"]["evaluation_coverage"] == 0.0

    markdown = render_markdown(report)
    assert "## Needs human review (1)" in markdown
    assert "Ambiguous free-text case" in markdown
