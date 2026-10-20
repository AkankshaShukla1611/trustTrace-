"""
Automated version of scripts/seed_covenace_demo.py's scenario, so the
CovenAce pack's acceptance demonstration (section 13.6 of the project
brief) is enforced by CI, not just a manually-run script. Every expected
value here traces back to a real source document -- see
app/evaluation_packs/covenace_pack/README.md for the citation of each one.
"""
import json
from pathlib import Path

from app.enums import ExecutionStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.document import DocumentFixture
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version
from app.runner.regression import compare_runs, evaluate_release_gate

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent / "app" / "evaluation_packs" / "covenace_pack" / "fixtures"
)

OUTPUT_YEAR_HITL_FLAGS = [
    "HITL - Confirm if there is any change in the management from last year",
    "HITL - RM: please confirm the reason for the net sales increase",
    "HITL - RM: please confirm the reason for the SG&A increase",
    "HITL - historical performance trend is based on only FY23 and FY24",
    "HITL - RM: please confirm the reason for the working capital increase",
    "HITL - risks & mitigants carried from last year's memo; update per latest scenario (Key Risks #1)",
    "HITL - risks & mitigants carried from last year's memo; update per latest scenario (Key Risks #2)",
    "HITL - PD and LGD grade not explicitly supported by source documents; human confirmation required",
]


def _load(filename: str) -> list[dict]:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def _seed(db_session):
    project = Project(name="CovenAce test project")
    pack = EvaluationPack(slug="covenace_credit_memo_test", name="CovenAce Pack (test)")
    db_session.add_all([project, pack])
    db_session.flush()

    baseline_integration = Integration(
        project_id=project.id, name="baseline", adapter_type=IntegrationType.FILE,
        config={"output_variant": "prior_year"},
    )
    candidate_integration = Integration(
        project_id=project.id, name="candidate", adapter_type=IntegrationType.FILE,
        config={"output_variant": "output_year"},
    )
    db_session.add_all([baseline_integration, candidate_integration])

    db_session.add_all(
        [
            DocumentFixture(
                id="covenant_calc_whole_eagle", project_id=project.id,
                filename="covenant_calc_whole_eagle.json", doc_type="extracted",
                pages=_load("covenant_calc_whole_eagle.json"),
            ),
            DocumentFixture(
                id="cashflow_coverage_whole_eagle", project_id=project.id,
                filename="cashflow_coverage_whole_eagle.json", doc_type="extracted",
                pages=_load("cashflow_coverage_whole_eagle.json"),
            ),
        ]
    )

    dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="Whole Eagle test dataset")
    db_session.add(dataset)
    db_session.flush()

    cases = {
        "net_sales_pass": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Net sales extraction",
            category="extraction", severity="medium", behavior_type="exact_fields",
            input_payload={"supplied_output": {"net_sales_2024": 278900}},
            expected_output={"net_sales_2024": 278884},
            evaluator_config={"factual_correctness": {"field_rules": {"net_sales_2024": {"type": "numeric_tolerance", "tolerance": 100}}}},
        ),
        "dscr_wrong_value_fail": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="DSCR incorrect value",
            category="extraction", severity="high", behavior_type="exact_fields",
            input_payload={"supplied_output": {"fy2024_dscr": 3.26}},
            expected_output={"fy2024_dscr": 2.64},
            evaluator_config={"factual_correctness": {"field_rules": {"fy2024_dscr": {"type": "numeric_tolerance", "tolerance": 0.05}}}},
        ),
        "dscr_citation_fail": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="DSCR wrong citation",
            category="citation", severity="high", behavior_type="free_text",
            input_payload={
                "supplied_output": {
                    "answer": "FY2024 debt service coverage was approximately 3.26x.",
                    "citations": [{"document_id": "cashflow_coverage_whole_eagle", "page": 1}],
                }
            },
            expected_evidence=[{"document_id": "covenant_calc_whole_eagle", "page": 1}],
        ),
        "conflict_not_flagged_fail": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="DSCR conflict not flagged",
            category="conflict", severity="critical", behavior_type="conflict_flag_expected",
            input_payload={"supplied_output": {"fields": {"fy2024_dscr": {"status": "ok", "value": "3.26x"}}}},
            evaluator_config={"conflict_detection": {"expected_conflict_fields": ["fy2024_dscr"]}},
        ),
        "missing_covenant_pass": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Missing covenant threshold",
            category="missing_info", severity="high", behavior_type="free_text",
            input_payload={"supplied_output": {"fields": {"contractual_min_dscr_covenant": {"status": "missing", "value": None}}}},
            evaluator_config={"missing_field": {"expected_missing_fields": ["contractual_min_dscr_covenant"]}},
        ),
        "invented_covenant_fail": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="Invented covenant threshold (controlled)",
            category="missing_info", severity="high", behavior_type="free_text",
            input_payload={"supplied_output": {"fields": {"contractual_min_dscr_covenant": {"status": "ok", "value": "1.25x"}}}},
            evaluator_config={"missing_field": {"expected_missing_fields": ["contractual_min_dscr_covenant"]}},
        ),
        "hitl_gate_regression": TestCase(
            dataset_id=dataset.id, evaluation_pack_id=pack.id, name="HITL gate (regression case)",
            category="hitl", severity="critical", behavior_type="free_text",
            input_payload={
                "supplied_outputs": {
                    "prior_year": {"unresolved_hitl_flags": []},
                    "output_year": {"unresolved_hitl_flags": OUTPUT_YEAR_HITL_FLAGS},
                }
            },
            evaluator_config={"hitl_gate": {"flags_field": "unresolved_hitl_flags", "required_clear": True}},
        ),
    }
    db_session.add_all(cases.values())
    db_session.flush()

    dataset_version = DatasetVersion(
        dataset_id=dataset.id, version_number=1,
        test_case_snapshot=[{"test_case_id": tc.id, "content_hash": "x"} for tc in cases.values()],
    )
    db_session.add(dataset_version)
    db_session.commit()

    return project, baseline_integration, candidate_integration, dataset_version, cases


def test_covenace_acceptance_demonstration_end_to_end(db_session):
    project, baseline_integration, candidate_integration, dataset_version, cases = _seed(db_session)

    baseline_run = run_dataset_version(
        db_session, project_id=project.id, integration_id=baseline_integration.id,
        dataset_version_id=dataset_version.id, label="baseline",
    )
    candidate_run = run_dataset_version(
        db_session, project_id=project.id, integration_id=candidate_integration.id,
        dataset_version_id=dataset_version.id, label="candidate", baseline_run_id=baseline_run.id,
    )

    baseline_status = {e.test_case_id: e.status for e in baseline_run.executions}
    candidate_status = {e.test_case_id: e.status for e in candidate_run.executions}

    # 1. correctly extracted field passes
    assert baseline_status[cases["net_sales_pass"].id] == ExecutionStatus.PASSED
    # 2. incorrect numeric value fails
    assert baseline_status[cases["dscr_wrong_value_fail"].id] == ExecutionStatus.FAILED
    # 3. unsupported/wrong citation fails
    assert baseline_status[cases["dscr_citation_fail"].id] == ExecutionStatus.FAILED
    # 5. conflicting value that should be flagged, isn't -- genuinely fails
    assert baseline_status[cases["conflict_not_flagged_fail"].id] == ExecutionStatus.FAILED
    # 4. missing value correctly reported missing, not invented
    assert baseline_status[cases["missing_covenant_pass"].id] == ExecutionStatus.PASSED
    assert baseline_status[cases["invented_covenant_fail"].id] == ExecutionStatus.FAILED
    # 6. HITL gate passes when no unresolved flags remain (prior_year variant)
    assert baseline_status[cases["hitl_gate_regression"].id] == ExecutionStatus.PASSED
    # ...and fails once real unresolved HITL flags are present (output_year variant)
    assert candidate_status[cases["hitl_gate_regression"].id] == ExecutionStatus.FAILED

    # 7. regression comparison detects the controlled regression, and the
    # release gate blocks on it because it's a critical-severity test case.
    summary = compare_runs(db_session, baseline_run.id, candidate_run.id)
    assert summary["new_failures"] == [cases["hitl_gate_regression"].id]
    assert cases["hitl_gate_regression"].id in summary["critical_failures"]

    gate = evaluate_release_gate(summary, {"block_on_critical": True})
    assert gate["passed"] is False
