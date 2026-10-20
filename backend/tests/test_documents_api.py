"""
API-level tests for document fixture upload, through FastAPI's
TestClient and real pypdf extraction (a hand-built minimal PDF, not a
mock) -- plus monkeypatched OCR for the scanned-PDF fallback path,
which needs no real Mistral key or network call.
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.models  # noqa: F401
from app.main import app
from app.services import ocr_service

# A minimal, hand-built, valid single-page PDF with real extractable text
# ("Hello TrustTrace") -- no reportlab/fpdf dependency needed just for a
# test. Offsets in the xref table are computed exactly (pypdf's recovery
# scan is not lenient enough to parse a PDF with a merely-approximate one).
_MINIMAL_PDF_TEXT = "Hello TrustTrace, this is a real native PDF text page."


def _build_minimal_pdf(text: str) -> bytes:
    content_stream = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n" + content_stream + b"\nendstream",
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(buf)
    n = len(objects) + 1
    xref = f"xref\n0 {n}\n0000000000 65535 f \n".encode()
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode()
    buf += xref
    buf += f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(buf)


_MINIMAL_PDF_BYTES = _build_minimal_pdf(_MINIMAL_PDF_TEXT)


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def project_id(client):
    return client.post("/projects", json={"name": "Doc upload test project"}).json()["id"]


def test_upload_native_text_pdf_extracts_real_text(client, project_id):
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("sample.pdf", io.BytesIO(_MINIMAL_PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["doc_type"] == "pdf_native"
    assert body["extraction_status"] == "ok"
    assert body["page_count"] == 1
    assert _MINIMAL_PDF_TEXT in body["pages"][0]["text"]


def test_upload_txt_file(client, project_id):
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("notes.txt", io.BytesIO(b"plain text fixture content"), "text/plain")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["doc_type"] == "text"
    assert body["pages"][0]["text"] == "plain text fixture content"


def test_upload_json_with_pages_shape(client, project_id):
    payload = b'{"pages": [{"page_number": 1, "text": "page one"}, {"page_number": 2, "text": "page two"}]}'
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("fixture.json", io.BytesIO(payload), "application/json")},
    )
    body = response.json()
    assert body["extraction_status"] == "ok"
    assert body["page_count"] == 2


def test_upload_json_with_unrecognized_shape_is_stored_verbatim_with_a_note(client, project_id):
    payload = b'{"borrower": "Acme Inc", "amount": 500000}'
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("odd.json", io.BytesIO(payload), "application/json")},
    )
    body = response.json()
    assert body["extraction_status"] == "ok"
    assert "did not match the expected pages shape" in body["extraction_notes"]
    assert "Acme Inc" in body["pages"][0]["text"]


def test_upload_rejects_unsupported_file_type(client, project_id):
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("virus.exe", io.BytesIO(b"not really"), "application/octet-stream")},
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client, project_id):
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_unknown_project(client):
    response = client.post(
        "/projects/does-not-exist/documents",
        files={"file": ("notes.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 404


def test_upload_scanned_pdf_without_ocr_configured_is_marked_partial(client, project_id, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: [{"page_number": 1, "text": ""}])

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("scanned.pdf", io.BytesIO(b"%PDF-1.4 fake scanned pdf bytes"), "application/pdf")},
    )
    body = response.json()
    assert body["extraction_status"] == "partial"
    assert "no OCR provider is configured" in body["extraction_notes"]
    assert body["doc_type"] == "pdf_native"


def test_upload_scanned_pdf_with_ocr_configured_succeeds_and_is_marked_pdf_ocr(client, project_id, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: [{"page_number": 1, "text": ""}])
    monkeypatch.setattr(
        ocr_service, "run_mistral_ocr",
        lambda b, f, **kw: [{"page_number": 1, "text": "Recovered via OCR: a sufficiently long passage of text."}],
    )

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("scanned.pdf", io.BytesIO(b"%PDF-1.4 fake scanned pdf bytes"), "application/pdf")},
    )
    body = response.json()
    assert body["extraction_status"] == "ok"
    assert body["doc_type"] == "pdf_ocr"
    assert "Recovered via OCR" in body["pages"][0]["text"]


def test_list_documents_omits_pages_but_get_one_includes_them(client, project_id):
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("notes.txt", io.BytesIO(b"some content"), "text/plain")},
    )
    listed = client.get(f"/projects/{project_id}/documents").json()
    assert len(listed) == 1
    assert "pages" not in listed[0]

    fetched = client.get(f"/documents/{listed[0]['id']}").json()
    assert fetched["pages"][0]["text"] == "some content"
