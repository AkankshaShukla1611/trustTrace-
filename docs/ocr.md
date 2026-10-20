# OCR fallback for scanned PDFs

`backend/app/services/ocr_service.py` extracts text from uploaded PDF
document fixtures (`POST /projects/{project_id}/documents`).

## Behavior

1. Try native text extraction (`pypdf`) first. This needs no API key and
   works for any ordinary (non-scanned) PDF.
2. If the result looks like a scanned/image PDF (average under ~20
   characters of text per page), and `MISTRAL_API_KEY` is set, fall back to
   Mistral's OCR API.
3. If OCR isn't configured, or the OCR call itself fails for any reason,
   the document is still created but marked `extraction_status: "partial"`
   with an explicit `extraction_notes` string -- it is never silently
   reported as fully read when it wasn't.

This matches the project's rule: "clearly report extraction failures or
OCR limitations rather than treating unreadable content as correctly
extracted."

## Mistral OCR API contract (verified against docs.mistral.ai, not assumed)

There's no documented way to pass raw PDF bytes inline to the OCR
endpoint, so this goes through Mistral's file-upload flow -- three real
HTTP calls, not one:

1. `POST https://api.mistral.ai/v1/files` -- multipart upload, field
   `file` plus `purpose=ocr`. Returns `{"id": "<file_id>", ...}`.
2. `GET https://api.mistral.ai/v1/files/{file_id}/url` -- returns a
   short-lived `{"url": "..."}` for that file.
3. `POST https://api.mistral.ai/v1/ocr` with
   `{"model": "mistral-ocr-latest", "document": {"type": "document_url", "document_url": "<signed url>"}}`.
   Returns `{"pages": [{"index": ..., "markdown": "...", ...}], "model": ..., "usage_info": {...}}`.
   Each page's text is in `markdown`.

All three calls use `Authorization: Bearer $MISTRAL_API_KEY`.

## Enabling it

Set `MISTRAL_API_KEY` in `backend/.env` (see `.env.example`). Nothing else
changes -- the fallback only activates when native extraction looks like
it missed real content, so ordinary PDFs never incur the extra network
calls or cost.

## What's NOT handled

- Tables and complex layouts: `markdown` from OCR is treated as plain
  page text, same as native extraction. No separate table/structure
  parsing.
- No file-size-based routing straight to OCR -- the native-extraction
  check always runs first, by design, to avoid an unnecessary OCR call
  (and its cost) for normal text PDFs.
