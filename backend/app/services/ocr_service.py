"""
PDF text extraction with an optional Mistral OCR fallback for
scanned/image-based PDFs. Mirrors the project's stance on document
processing: never pretend a page was read when it wasn't.

Flow:
  1. Always try native text extraction first (pypdf) -- works for
     ordinary, non-scanned PDFs with no API key or network call needed.
  2. If that yields suspiciously little text per page (a strong signal
     the PDF is scanned/image-based) AND MISTRAL_API_KEY is configured,
     fall back to Mistral's OCR API.
  3. If OCR isn't configured, or the OCR call itself fails, the
     extraction is reported as "partial" with an explicit note -- never
     silently upgraded to "ok".

Mistral OCR's real REST contract (confirmed against docs.mistral.ai,
not guessed) is three calls: upload the file (POST /v1/files, purpose
"ocr"), fetch a short-lived signed URL for it (GET /v1/files/{id}/url),
then call OCR with that URL (POST /v1/ocr). There is no documented way
to pass raw bytes inline, so this module always goes through the
upload step.
"""
from __future__ import annotations
import io
import os

import httpx
from pypdf import PdfReader

MISTRAL_BASE_URL = "https://api.mistral.ai"
MIN_CHARS_PER_PAGE_THRESHOLD = 20


def extract_native_pdf_text(file_bytes: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append({"page_number": i, "text": text})
    return pages


def looks_unreadable(pages: list[dict]) -> bool:
    """True if native extraction almost certainly missed real content (e.g. a scanned PDF)."""
    if not pages:
        return True
    avg_chars = sum(len(p["text"]) for p in pages) / len(pages)
    return avg_chars < MIN_CHARS_PER_PAGE_THRESHOLD


def run_mistral_ocr(file_bytes: bytes, filename: str, *, timeout_seconds: float = 60.0) -> list[dict]:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    headers = {"Authorization": f"Bearer {api_key}"}

    with httpx.Client(base_url=MISTRAL_BASE_URL, timeout=timeout_seconds) as client:
        upload_response = client.post(
            "/v1/files",
            headers=headers,
            data={"purpose": "ocr"},
            files={"file": (filename, file_bytes, "application/pdf")},
        )
        upload_response.raise_for_status()
        file_id = upload_response.json()["id"]

        url_response = client.get(f"/v1/files/{file_id}/url", headers=headers)
        url_response.raise_for_status()
        signed_url = url_response.json()["url"]

        ocr_response = client.post(
            "/v1/ocr",
            headers=headers,
            json={
                "model": "mistral-ocr-latest",
                "document": {"type": "document_url", "document_url": signed_url},
            },
        )
        ocr_response.raise_for_status()
        result = ocr_response.json()

    # Use positional order (1-indexed) rather than the API's own "index" field,
    # whose zero- vs one-indexing isn't confirmed in Mistral's docs -- this
    # keeps page numbering consistent with the rest of TrustTrace regardless.
    return [
        {"page_number": position, "text": page.get("markdown", "")}
        for position, page in enumerate(result.get("pages", []), start=1)
    ]


def extract_pdf(file_bytes: bytes, filename: str) -> tuple[list[dict], str, str | None]:
    """Returns (pages, extraction_status, extraction_notes). Status is one of ok|partial|failed."""
    try:
        native_pages = extract_native_pdf_text(file_bytes)
    except Exception as exc:
        return [], "failed", f"native PDF text extraction failed: {type(exc).__name__}: {exc}"

    if not looks_unreadable(native_pages):
        return native_pages, "ok", None

    if not os.environ.get("MISTRAL_API_KEY"):
        return native_pages, "partial", (
            "Native text extraction found very little text per page (likely a scanned/image PDF) "
            "and no OCR provider is configured -- set MISTRAL_API_KEY to enable the OCR fallback. "
            "Pages below are whatever native extraction returned, which may be empty or incomplete."
        )

    try:
        ocr_pages = run_mistral_ocr(file_bytes, filename)
    except Exception as exc:
        return native_pages, "partial", (
            f"OCR fallback failed ({type(exc).__name__}: {exc}); native extraction (likely incomplete for a "
            "scanned PDF) is what's stored below."
        )

    if looks_unreadable(ocr_pages):
        return ocr_pages, "partial", "OCR ran but still returned very little text per page -- document may be blank, corrupted, or unsupported."

    return ocr_pages, "ok", "text recovered via Mistral OCR fallback (native extraction found little text)"
