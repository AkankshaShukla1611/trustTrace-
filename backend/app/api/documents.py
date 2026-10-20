from __future__ import annotations
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import DocumentFixture
from app.models.project import Project
from app.serializers import document_fixture_dict
from app.services.ocr_service import extract_pdf

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {"pdf", "txt", "json"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB -- generous for test fixtures, not a production ingest limit


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_txt(content: bytes) -> tuple[list[dict], str, str | None]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return [], "failed", "file is not valid UTF-8 text"
    return [{"page_number": 1, "text": text}], "ok", None


def _extract_json(content: bytes) -> tuple[list[dict], str, str | None]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return [], "failed", f"not valid JSON: {exc}"

    if isinstance(data, list) and all(isinstance(p, dict) and "text" in p for p in data):
        pages = [
            {"page_number": p.get("page_number", i + 1), "text": p["text"]} for i, p in enumerate(data)
        ]
        return pages, "ok", None

    if isinstance(data, dict) and isinstance(data.get("pages"), list):
        pages = data["pages"]
        return pages, "ok", None

    # Arbitrary JSON that doesn't match the {"pages": [...]} / [{"text": ...}]
    # shape -- store it verbatim as one page rather than guessing a structure.
    return (
        [{"page_number": 1, "text": json.dumps(data, indent=2)}],
        "ok",
        "JSON did not match the expected pages shape ({\"pages\": [...]} or [{\"text\": ...}, ...]); stored verbatim as a single page.",
    )


@router.post("/projects/{project_id}/documents")
async def upload_document(project_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    extension = _extension(file.filename or "")
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"unsupported file type '.{extension}' -- allowed: {sorted(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit")
    if len(content) == 0:
        raise HTTPException(400, "uploaded file is empty")

    if extension == "pdf":
        pages, status, notes = extract_pdf(content, file.filename)
        used_ocr = status == "ok" and notes is not None and "OCR" in notes
        doc_type = "pdf_ocr" if used_ocr else "pdf_native"
    elif extension == "txt":
        pages, status, notes = _extract_txt(content)
        doc_type = "text"
    else:
        pages, status, notes = _extract_json(content)
        doc_type = "json"

    document = DocumentFixture(
        project_id=project_id,
        filename=file.filename,
        doc_type=doc_type,
        pages=pages,
        extraction_status=status,
        extraction_notes=notes,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document_fixture_dict(document)


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: str, db: Session = Depends(get_db)):
    documents = db.query(DocumentFixture).filter(DocumentFixture.project_id == project_id).all()
    return [document_fixture_dict(d, include_pages=False) for d in documents]


@router.get("/documents/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(DocumentFixture, document_id)
    if document is None:
        raise HTTPException(404, "document not found")
    return document_fixture_dict(document)
