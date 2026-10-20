"""
Unit tests for the OCR fallback logic. No real PDF binary or API key is
needed: native extraction is exercised through looks_unreadable()
directly (pypdf's own extraction is third-party-tested), and the
Mistral HTTP flow is monkeypatched so these tests never make a real
network call or require a key -- but they do verify the exact 3-call
contract documented in docs/ocr.md.
"""
import pytest

from app.services import ocr_service


def test_looks_unreadable_true_for_empty_pages():
    assert ocr_service.looks_unreadable([]) is True


def test_looks_unreadable_true_for_near_empty_text():
    assert ocr_service.looks_unreadable([{"page_number": 1, "text": ""}, {"page_number": 2, "text": "x"}]) is True


def test_looks_unreadable_false_for_real_text():
    pages = [{"page_number": 1, "text": "This page has a normal amount of real extracted text content on it."}]
    assert ocr_service.looks_unreadable(pages) is False


def test_extract_pdf_reports_partial_with_no_api_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: [{"page_number": 1, "text": ""}])

    pages, status, notes = ocr_service.extract_pdf(b"fake-pdf-bytes", "scanned.pdf")

    assert status == "partial"
    assert "no OCR provider is configured" in notes
    assert pages == [{"page_number": 1, "text": ""}]  # whatever native extraction returned, not dropped


def test_extract_pdf_returns_ok_without_ocr_when_native_text_is_sufficient(monkeypatch):
    real_pages = [{"page_number": 1, "text": "Plenty of real native text content extracted from this page."}]
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: real_pages)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("OCR should not be called when native extraction already succeeded")

    monkeypatch.setattr(ocr_service, "run_mistral_ocr", fail_if_called)

    pages, status, notes = ocr_service.extract_pdf(b"fake-pdf-bytes", "normal.pdf")
    assert status == "ok"
    assert notes is None
    assert pages == real_pages


def test_extract_pdf_falls_back_to_ocr_when_configured_and_succeeds(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: [{"page_number": 1, "text": ""}])

    ocr_pages = [{"page_number": 1, "text": "Recovered via OCR: a long enough passage of real text."}]
    monkeypatch.setattr(ocr_service, "run_mistral_ocr", lambda b, f, **kw: ocr_pages)

    pages, status, notes = ocr_service.extract_pdf(b"fake-pdf-bytes", "scanned.pdf")
    assert status == "ok"
    assert "OCR" in notes
    assert pages == ocr_pages


def test_extract_pdf_reports_partial_when_ocr_call_itself_fails(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key-for-test")
    native_pages = [{"page_number": 1, "text": ""}]
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: native_pages)

    def raise_error(*args, **kwargs):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(ocr_service, "run_mistral_ocr", raise_error)

    pages, status, notes = ocr_service.extract_pdf(b"fake-pdf-bytes", "scanned.pdf")
    assert status == "partial"
    assert "OCR fallback failed" in notes
    assert "401 Unauthorized" in notes
    assert pages == native_pages


def test_extract_pdf_reports_partial_when_ocr_also_returns_little_text(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", lambda b: [{"page_number": 1, "text": ""}])
    monkeypatch.setattr(ocr_service, "run_mistral_ocr", lambda b, f, **kw: [{"page_number": 1, "text": ""}])

    pages, status, notes = ocr_service.extract_pdf(b"fake-pdf-bytes", "blank.pdf")
    assert status == "partial"
    assert "still returned very little text" in notes


def test_extract_pdf_reports_failed_when_native_extraction_raises(monkeypatch):
    def raise_error(b):
        raise ValueError("not a PDF")

    monkeypatch.setattr(ocr_service, "extract_native_pdf_text", raise_error)

    pages, status, notes = ocr_service.extract_pdf(b"not-a-real-pdf", "broken.pdf")
    assert status == "failed"
    assert pages == []
    assert "not a PDF" in notes


def test_run_mistral_ocr_raises_clearly_without_api_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        ocr_service.run_mistral_ocr(b"bytes", "file.pdf")


def test_run_mistral_ocr_follows_the_documented_three_call_contract(monkeypatch):
    """
    Verifies the exact upload -> signed-url -> ocr sequence documented in
    docs/ocr.md by faking httpx.Client -- proves the code calls the right
    endpoints in the right order with the right auth header, without
    needing network access or a real key.
    """
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key-for-test")
    calls = []

    class FakeResponse:
        def __init__(self, json_data):
            self._json = json_data

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, path, **kwargs):
            calls.append(("POST", path, kwargs))
            if path == "/v1/files":
                return FakeResponse({"id": "file_abc123"})
            if path == "/v1/ocr":
                return FakeResponse({"pages": [{"index": 0, "markdown": "page one text"}]})
            raise AssertionError(f"unexpected POST to {path}")

        def get(self, path, **kwargs):
            calls.append(("GET", path, kwargs))
            assert path == "/v1/files/file_abc123/url"
            return FakeResponse({"url": "https://signed.example.com/file_abc123"})

    monkeypatch.setattr(ocr_service.httpx, "Client", FakeClient)

    pages = ocr_service.run_mistral_ocr(b"pdf-bytes", "doc.pdf")

    assert [c[:2] for c in calls] == [
        ("POST", "/v1/files"),
        ("GET", "/v1/files/file_abc123/url"),
        ("POST", "/v1/ocr"),
    ]
    for _, _, kwargs in calls:
        assert kwargs["headers"]["Authorization"] == "Bearer fake-key-for-test"

    ocr_call_body = calls[2][2]["json"]
    assert ocr_call_body["document"] == {"type": "document_url", "document_url": "https://signed.example.com/file_abc123"}
    assert pages == [{"page_number": 1, "text": "page one text"}]
