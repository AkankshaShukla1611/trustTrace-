"""
Seeds the CovenAce evaluation pack (file/batch mode -- see
app/evaluation_packs/covenace_pack/README.md for exactly why live
execution isn't available yet, and for the provenance of every figure
used below). Every expected value and every "actual output" here was
read directly out of the real source documents during analysis -- see
that README for the specific citation of each one. Nothing here is a
score invented to make a demo look good.

Usage (from backend/):
    python scripts/seed_covenace_demo.py
"""
from __future__ import annotations
import json
from pathlib import Path

from app.adapters.file_adapter import FileAdapter
from app.database import SessionLocal, init_db
from app.enums import IntegrationStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.document import DocumentFixture
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version
from app.runner.regression import compare_runs, evaluate_release_gate

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "app" / "evaluation_packs" / "covenace_pack" / "fixtures"

# The 8 unresolved HITL/HILT markers literally present in the Output Year
# memo's own text (verified by grep against the extracted .docx text).
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


def _load_fixture_pages(filename: str) -> list[dict]:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Project).filter(Project.name == "CovenAce Demo (synthetic Whole Eagle)").first()
        if existing:
            print("CovenAce demo project already exists; skipping seed.")
            return

        project = Project(
            name="CovenAce Demo (synthetic Whole Eagle)",
            description=(
                "File/batch evaluation of a synthetic C&I credit review case. Live CovenAce "
                "execution is not yet connected -- see app/evaluation_packs/covenace_pack/README.md."
            ),
        )
        pack = EvaluationPack(
            slug="covenace_credit_memo", name="CovenAce Credit Memo Pack", version="0.1.0",
            description="Covenant extraction / credit memo evaluation, file/batch mode only.",
        )
        db.add_all([project, pack])
        db.flush()

        baseline_integration = Integration(
            project_id=project.id, name="File adapter (prior_year variant)",
            adapter_type=IntegrationType.FILE, config={"output_variant": "prior_year"},
            status=IntegrationStatus.CONNECTED,
            capabilities=FileAdapter({"output_variant": "prior_year"}).get_capabilities().as_dict(),
        )
        candidate_integration = Integration(
            project_id=project.id, name="File adapter (output_year variant)",
            adapter_type=IntegrationType.FILE, config={"output_variant": "output_year"},
            status=IntegrationStatus.CONNECTED,
            capabilities=FileAdapter({"output_variant": "output_year"}).get_capabilities().as_dict(),
        )
        db.add_all([baseline_integration, candidate_integration])

        for doc_id, filename in [
            ("wholeeagle_fy24_pdf", "wholeeagle_fy24_pdf.json"),
            ("cashflow_coverage_whole_eagle", "cashflow_coverage_whole_eagle.json"),
            ("covenant_calc_whole_eagle", "covenant_calc_whole_eagle.json"),
        ]:
            db.add(
                DocumentFixture(
                    id=doc_id, project_id=project.id, filename=filename, doc_type="extracted",
                    pages=_load_fixture_pages(filename),
                )
            )

        dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="Whole Eagle FY24 review dataset")
        db.add(dataset)
        db.flush()

        cases = [
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Net sales extraction matches source financial statements", category="extraction",
                severity="medium", behavior_type="exact_fields",
                input_payload={
                    "supplied_output": {
                        "net_sales_2024": 278900,
                        "answer": "Net sales increased to $278.9 million in 2024 from $268.4 million in 2023.",
                        "citations": [{"document_id": "wholeeagle_fy24_pdf", "page": 3}],
                    }
                },
                expected_output={"net_sales_2024": 278884},
                evaluator_config={"factual_correctness": {"field_rules": {"net_sales_2024": {"type": "numeric_tolerance", "tolerance": 100}}}},
                expected_evidence=[{"document_id": "wholeeagle_fy24_pdf", "page": 3}],
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="FY2024 DSCR cited in memo does not match the covenant-testing workbook",
                category="extraction", severity="high", behavior_type="exact_fields",
                input_payload={"supplied_output": {"fy2024_dscr": 3.26}},
                expected_output={"fy2024_dscr": 2.64},
                evaluator_config={"factual_correctness": {"field_rules": {"fy2024_dscr": {"type": "numeric_tolerance", "tolerance": 0.05}}}},
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="FY2024 DSCR claim cites the wrong source workbook", category="citation",
                severity="high", behavior_type="free_text",
                input_payload={
                    "supplied_output": {
                        "answer": "FY2024 debt service coverage was approximately 3.26x.",
                        "citations": [{"document_id": "cashflow_coverage_whole_eagle", "page": 1}],
                    }
                },
                expected_evidence=[{"document_id": "covenant_calc_whole_eagle", "page": 1}],
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Conflicting FY2024 DSCR across source workbooks is not flagged", category="conflict",
                severity="critical", behavior_type="conflict_flag_expected",
                input_payload={"supplied_output": {"fields": {"fy2024_dscr": {"status": "ok", "value": "3.26x"}}}},
                evaluator_config={"conflict_detection": {"expected_conflict_fields": ["fy2024_dscr"]}},
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Undocumented contractual DSCR covenant threshold reported missing", category="missing_info",
                severity="high", behavior_type="free_text",
                input_payload={"supplied_output": {"fields": {"contractual_min_dscr_covenant": {"status": "missing", "value": None}}}},
                evaluator_config={"missing_field": {"expected_missing_fields": ["contractual_min_dscr_covenant"]}},
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Controlled test: inventing the undocumented covenant threshold must fail",
                category="missing_info", severity="high", behavior_type="free_text",
                input_payload={"supplied_output": {"fields": {"contractual_min_dscr_covenant": {"status": "ok", "value": "1.25x"}}}},
                evaluator_config={"missing_field": {"expected_missing_fields": ["contractual_min_dscr_covenant"]}},
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Credit memo has no unresolved human-in-the-loop review flags", category="hitl",
                severity="critical", behavior_type="free_text",
                input_payload={
                    "supplied_outputs": {
                        "prior_year": {"unresolved_hitl_flags": []},
                        "output_year": {"unresolved_hitl_flags": OUTPUT_YEAR_HITL_FLAGS},
                    }
                },
                evaluator_config={"hitl_gate": {"flags_field": "unresolved_hitl_flags", "required_clear": True}},
            ),
        ]
        db.add_all(cases)
        db.flush()

        dataset_version = DatasetVersion(
            dataset_id=dataset.id, version_number=1,
            test_case_snapshot=[{"test_case_id": c.id, "content_hash": "covenace-seed-v1"} for c in cases],
        )
        db.add(dataset_version)
        db.commit()

        baseline_run = run_dataset_version(
            db, project_id=project.id, integration_id=baseline_integration.id,
            dataset_version_id=dataset_version.id, label="Prior Year memo (baseline)",
        )
        print(f"Baseline run {baseline_run.id} (prior_year variant):")
        for execution in baseline_run.executions:
            case = next(c for c in cases if c.id == execution.test_case_id)
            print(f"  [{execution.status}] {case.name}")

        candidate_run = run_dataset_version(
            db, project_id=project.id, integration_id=candidate_integration.id,
            dataset_version_id=dataset_version.id, label="Output Year memo (candidate)",
            baseline_run_id=baseline_run.id,
        )
        print(f"\nCandidate run {candidate_run.id} (output_year variant):")
        for execution in candidate_run.executions:
            case = next(c for c in cases if c.id == execution.test_case_id)
            print(f"  [{execution.status}] {case.name}")

        summary = compare_runs(db, baseline_run.id, candidate_run.id)
        gate = evaluate_release_gate(summary, {"block_on_critical": True})
        print("\nRegression summary:", {k: v for k, v in summary.items() if k != "category_changes"})
        print("Release gate:", gate)
    finally:
        db.close()


if __name__ == "__main__":
    main()
