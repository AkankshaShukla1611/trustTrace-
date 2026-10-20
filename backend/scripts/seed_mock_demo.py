"""
Seeds a "Mock Demo" project with a small labeled dataset against the
MockAdapter (Layer D's deterministic example_app), then runs it, so the
platform has real, persisted, query-able data to demo against -- not
placeholder/fake numbers.

Usage (from backend/):
    python scripts/seed_mock_demo.py
"""
from __future__ import annotations

from app.adapters.mock_adapter import MockAdapter
from app.database import SessionLocal, init_db
from app.enums import IntegrationStatus, IntegrationType
from app.models.dataset import Dataset, DatasetVersion
from app.models.document import DocumentFixture
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.test_case import TestCase
from app.runner.engine import run_dataset_version
from app.runner.regression import compare_runs, evaluate_release_gate

DOCUMENTS = [
    {
        "document_id": "loan_agreement",
        "pages": [
            {
                "page_number": 1,
                "text": "The total loan amount disbursed to the borrower is 500000 dollars under this agreement.",
            },
            {
                "page_number": 2,
                "text": "The borrower shall maintain a minimum current ratio of 1.5 at all times.",
            },
        ],
    },
    {
        "document_id": "amendment_1",
        "pages": [
            {"page_number": 1, "text": "This amendment revises the total loan amount disbursed to 600000 dollars."}
        ],
    },
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Project).filter(Project.name == "Mock Demo Project").first()
        if existing:
            print(f"Mock Demo Project already exists (id={existing.id}); skipping seed.")
            return

        project = Project(name="Mock Demo Project", description="Proves the generic TrustTrace engine end to end with no external API.")
        pack = EvaluationPack(slug="mock_financial_qa", name="Mock Financial QA Pack", version="1.0.0")
        db.add_all([project, pack])
        db.flush()

        integration = Integration(
            project_id=project.id, name="Mock Adapter", adapter_type=IntegrationType.MOCK, config={},
            status=IntegrationStatus.CONNECTED, capabilities=MockAdapter({}).get_capabilities().as_dict(),
        )
        for doc in DOCUMENTS:
            db.add(
                DocumentFixture(
                    id=doc["document_id"],
                    project_id=project.id,
                    filename=f"{doc['document_id']}.txt",
                    doc_type="synthetic",
                    pages=doc["pages"],
                )
            )
        dataset = Dataset(project_id=project.id, evaluation_pack_id=pack.id, name="Mock financial QA dataset")
        db.add_all([integration, dataset])
        db.flush()

        cases = [
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Extracts loan amount with grounded citation", category="extraction", severity="high",
                behavior_type="free_text",
                input_payload={"mode": "qa", "query": "total loan amount disbursed", "documents": [DOCUMENTS[0]]},
                expected_evidence=[{"document_id": "loan_agreement", "page": 1}],
                relevant_passage_ids=["loan_agreement:p1"],
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Abstains when evidence is absent", category="abstention", severity="high",
                behavior_type="abstain_expected",
                input_payload={"mode": "qa", "query": "prepayment penalty clause details", "documents": [DOCUMENTS[0]]},
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Flags conflicting loan amount across agreement and amendment", category="conflict",
                severity="critical", behavior_type="conflict_flag_expected",
                input_payload={
                    "mode": "extract", "documents": DOCUMENTS,
                    "field_specs": [{"field_name": "loan_amount", "pattern": r"total loan amount disbursed (?:to the borrower is|to) (\d+)"}],
                },
                evaluator_config={"conflict_detection": {"expected_conflict_fields": ["loan_amount"]}},
            ),
            TestCase(
                dataset_id=dataset.id, evaluation_pack_id=pack.id,
                name="Missing field is reported missing, never invented", category="extraction", severity="medium",
                behavior_type="free_text",
                input_payload={
                    "mode": "extract", "documents": [DOCUMENTS[0]],
                    "field_specs": [{"field_name": "interest_rate", "pattern": r"interest rate of ([\d.]+)%"}],
                },
                evaluator_config={"missing_field": {"expected_missing_fields": ["interest_rate"]}},
            ),
        ]
        db.add_all(cases)
        db.flush()

        dataset_version = DatasetVersion(
            dataset_id=dataset.id, version_number=1,
            test_case_snapshot=[{"test_case_id": c.id, "content_hash": "seed-v1"} for c in cases],
        )
        db.add(dataset_version)
        db.commit()

        baseline_run = run_dataset_version(
            db, project_id=project.id, integration_id=integration.id,
            dataset_version_id=dataset_version.id, label="Baseline run (normal mock adapter)",
        )
        print(f"Seeded project {project.id}, dataset_version {dataset_version.id}")
        print(f"Baseline run {baseline_run.id}:")
        for execution in baseline_run.executions:
            print(f"  [{execution.status}] {execution.test_case_id}")

        # A second integration pointed at a deliberately regressed
        # configuration of the same mock target (force_abstain=True),
        # to demonstrate a controlled, genuinely-detected regression --
        # not an edited/fabricated result.
        regressed_integration = Integration(
            project_id=project.id, name="Mock Adapter (regressed config)",
            adapter_type=IntegrationType.MOCK, config={"force_abstain": True},
            status=IntegrationStatus.CONNECTED,
            capabilities=MockAdapter({"force_abstain": True}).get_capabilities().as_dict(),
        )
        db.add(regressed_integration)
        db.commit()

        candidate_run = run_dataset_version(
            db, project_id=project.id, integration_id=regressed_integration.id,
            dataset_version_id=dataset_version.id, label="Candidate run (regressed config)",
            baseline_run_id=baseline_run.id,
        )
        print(f"Candidate run {candidate_run.id}:")
        for execution in candidate_run.executions:
            print(f"  [{execution.status}] {execution.test_case_id}")

        summary = compare_runs(db, baseline_run.id, candidate_run.id)
        gate = evaluate_release_gate(summary, {"block_on_critical": True, "max_new_failures": 0})
        print("Regression summary:", {k: v for k, v in summary.items() if k != "category_changes"})
        print("Release gate:", gate)
    finally:
        db.close()


if __name__ == "__main__":
    main()
