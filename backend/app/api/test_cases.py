from __future__ import annotations
import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dataset import Dataset
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseCreate, TestCaseImportRequest, TestCaseUpdate
from app.serializers import test_case_dict
from app.services.test_case_service import compute_content_hash, content_fields, validate_test_case_fields

router = APIRouter(tags=["test-cases"])

CSV_COLUMNS = [
    "id", "name", "description", "category", "tags", "severity", "behavior_type",
    "input_payload", "expected_output", "expected_evidence", "relevant_passage_ids",
    "expected_tool_calls", "prohibited_tool_calls", "evaluator_config", "preconditions",
    "version", "status",
]
CSV_JSON_FIELDS = {
    "tags", "input_payload", "expected_output", "expected_evidence", "relevant_passage_ids",
    "expected_tool_calls", "prohibited_tool_calls", "evaluator_config",
}


def _find_duplicate(db: Session, dataset_id: str, content_hash: str) -> TestCase | None:
    return (
        db.query(TestCase)
        .filter(TestCase.dataset_id == dataset_id, TestCase.content_hash == content_hash, TestCase.status == "active")
        .first()
    )


@router.post("/datasets/{dataset_id}/test-cases")
def create_test_case(dataset_id: str, payload: TestCaseCreate, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")

    data = payload.model_dump()
    errors = validate_test_case_fields(data)
    if errors:
        raise HTTPException(422, {"errors": errors})

    content_hash = compute_content_hash(content_fields(data))
    duplicate = _find_duplicate(db, dataset_id, content_hash)
    if duplicate:
        raise HTTPException(409, f"duplicate of existing test case '{duplicate.id}' (identical content)")

    test_case = TestCase(
        dataset_id=dataset_id, evaluation_pack_id=dataset.evaluation_pack_id,
        content_hash=content_hash, **data,
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case_dict(test_case)


@router.get("/datasets/{dataset_id}/test-cases")
def list_test_cases(
    dataset_id: str,
    category: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    status: str = "active",
    db: Session = Depends(get_db),
):
    query = db.query(TestCase).filter(TestCase.dataset_id == dataset_id)
    if status != "all":
        query = query.filter(TestCase.status == status)
    if category:
        query = query.filter(TestCase.category == category)
    if severity:
        query = query.filter(TestCase.severity == severity)

    cases = query.all()
    if tag:
        cases = [c for c in cases if tag in (c.tags or [])]
    if q:
        q_lower = q.lower()
        cases = [
            c for c in cases
            if q_lower in c.name.lower() or q_lower in (c.description or "").lower()
        ]
    return [test_case_dict(c) for c in cases]


@router.get("/test-cases/{test_case_id}")
def get_test_case(test_case_id: str, db: Session = Depends(get_db)):
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "test case not found")
    return test_case_dict(test_case)


@router.put("/test-cases/{test_case_id}")
def update_test_case(test_case_id: str, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "test case not found")

    data = payload.model_dump()
    errors = validate_test_case_fields(data)
    if errors:
        raise HTTPException(422, {"errors": errors})

    for field, value in data.items():
        setattr(test_case, field, value)
    test_case.content_hash = compute_content_hash(content_fields(data))
    test_case.version += 1
    db.commit()
    db.refresh(test_case)
    return test_case_dict(test_case)


@router.delete("/test-cases/{test_case_id}")
def archive_test_case(test_case_id: str, db: Session = Depends(get_db)):
    """
    Soft delete: archived test cases drop out of new listings and new
    dataset version snapshots, but stay in the database so any
    DatasetVersion that already snapshotted them can still reproduce
    that run.
    """
    test_case = db.get(TestCase, test_case_id)
    if test_case is None:
        raise HTTPException(404, "test case not found")
    test_case.status = "archived"
    db.commit()
    return {"id": test_case.id, "status": test_case.status}


@router.post("/datasets/{dataset_id}/test-cases/import")
def import_test_cases_json(dataset_id: str, payload: TestCaseImportRequest, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")

    allowed_fields = set(TestCaseCreate.model_fields)
    created, skipped, errors = [], [], []

    for index, raw in enumerate(payload.test_cases):
        field_errors = validate_test_case_fields(raw)
        if field_errors:
            errors.append({"index": index, "name": raw.get("name"), "errors": field_errors})
            continue

        content_hash = compute_content_hash(content_fields(raw))
        if not payload.allow_duplicates:
            duplicate = _find_duplicate(db, dataset_id, content_hash)
            if duplicate:
                skipped.append({"index": index, "name": raw.get("name"), "duplicate_of": duplicate.id})
                continue

        clean = {k: v for k, v in raw.items() if k in allowed_fields}
        test_case = TestCase(
            dataset_id=dataset_id, evaluation_pack_id=dataset.evaluation_pack_id,
            content_hash=content_hash, **clean,
        )
        db.add(test_case)
        db.flush()
        created.append(test_case.id)

    db.commit()
    return {"created": created, "skipped_duplicates": skipped, "errors": errors}


@router.get("/datasets/{dataset_id}/test-cases/export")
def export_test_cases(
    dataset_id: str, format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db)
):
    cases = db.query(TestCase).filter(TestCase.dataset_id == dataset_id, TestCase.status == "active").all()

    if format == "json":
        return [test_case_dict(c) for c in cases]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for case in cases:
        row = {}
        for column in CSV_COLUMNS:
            value = getattr(case, column)
            row[column] = json.dumps(value) if isinstance(value, (dict, list)) else value
        writer.writerow(row)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=test_cases_{dataset_id}.csv"},
    )


@router.post("/datasets/{dataset_id}/test-cases/import-csv")
async def import_test_cases_csv(
    dataset_id: str, file: UploadFile = File(...), allow_duplicates: bool = False, db: Session = Depends(get_db)
):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")

    raw_text = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw_text))

    parsed_rows = []
    for row in reader:
        parsed: dict = {}
        for key, value in row.items():
            if value == "":
                parsed[key] = None
            elif key in CSV_JSON_FIELDS:
                try:
                    parsed[key] = json.loads(value)
                except json.JSONDecodeError:
                    # left as the raw string so validate_test_case_fields reports it cleanly
                    parsed[key] = value
            else:
                parsed[key] = value
        parsed_rows.append(parsed)

    return import_test_cases_json(
        dataset_id, TestCaseImportRequest(test_cases=parsed_rows, allow_duplicates=allow_duplicates), db
    )
