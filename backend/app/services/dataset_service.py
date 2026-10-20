from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetVersion
from app.models.test_case import TestCase
from app.services.test_case_service import compute_content_hash


def create_dataset_version(db: Session, dataset_id: str) -> DatasetVersion:
    """
    Snapshots every currently-active test case in the dataset into an
    immutable version. Existing versions are untouched, so runs already
    started against an older version stay reproducible even if test
    cases are edited or archived afterward.
    """
    active_cases = (
        db.query(TestCase)
        .filter(TestCase.dataset_id == dataset_id, TestCase.status == "active")
        .all()
    )

    latest = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .first()
    )
    next_version_number = (latest.version_number + 1) if latest else 1

    snapshot = [
        {
            "test_case_id": tc.id,
            "content_hash": tc.content_hash or compute_content_hash(
                {field: getattr(tc, field) for field in [
                    "category", "severity", "behavior_type", "input_payload", "expected_output",
                    "expected_evidence", "relevant_passage_ids", "expected_tool_calls",
                    "prohibited_tool_calls", "evaluator_config",
                ]}
            ),
        }
        for tc in active_cases
    ]

    version = DatasetVersion(
        dataset_id=dataset_id, version_number=next_version_number, test_case_snapshot=snapshot
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
