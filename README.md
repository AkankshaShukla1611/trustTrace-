# TrustTrace

A generic AI evaluation, testing, and regression platform. TrustTrace tests
RAG apps, LLM document-processing workflows, extraction/classification
pipelines, and tool-using agents through one reusable core, pluggable
adapters, and per-application evaluation packs.

**Status:** backend (generic core, 2 evaluation packs, full API) is
implemented and tested. A React frontend now exists and builds cleanly, but
**could not be verified in a live browser in this environment** -- see
"Known limitation" below. See "What's implemented" for the exact boundary.

## Architecture

```
Layer A  Generic core        project/integration mgmt, test runner,
                              evaluation engine, persistence, regression
Layer B  Adapters             mock | http | python | file  (app/adapters/)
Layer C  Evaluation packs     per-application test cases + domain rules
                              (app/evaluation_packs/, DB-backed EvaluationPack)
```

See [docs/architecture.md](docs/architecture.md) for the full data model and
[docs/adapter_guide.md](docs/adapter_guide.md) for how to connect a new
target application without touching the core.

## What's implemented (verified by actually running it, not just written)

- **A second, real evaluation pack**: `app/evaluation_packs/covenace_pack/`,
  built from a confirmed-synthetic C&I credit review case (not invented
  figures -- every expected value in it was read out of real source
  documents during analysis; see that pack's README for the full
  provenance and citations). Runs through the `file` adapter since live
  CovenAce execution isn't connected yet (see "What's NOT yet implemented"
  and `docs/adapter_guide.md`). Demonstrates all 7 items from the CovenAce
  acceptance checklist -- a correct extraction passing, an incorrect
  numeric value failing, a wrong citation failing, a missing value
  correctly reported missing (plus a controlled contrast where inventing
  one fails), a real cross-document conflict that goes unflagged, an
  HITL-gate check, and a genuine regression between two runs (the newer of
  two real credit memos has 8 literal unresolved HITL review markers in
  its own text; the prior one has zero) -- enforced by
  `tests/test_covenace_pack_demo.py`, not just a one-off script.

- **Data models** for projects, integrations, evaluation packs, datasets +
  immutable dataset versions, test cases, document fixtures, runs, test
  executions, trace events, evaluator results, regression comparisons.
  SQLite + SQLAlchemy; `init_db()` creates all tables.
- **Four adapters** implementing the common contract: `mock` (wraps a
  deterministic example financial-document QA/extraction engine, no
  network/API needed), `http` (configurable REST integration, secrets
  resolved from environment variables, never stored in config), `python`
  (calls an already-installed function -- not arbitrary code execution),
  `file` (evaluates pre-exported outputs, explicitly marked as unable to
  test live execution).
- **Seven deterministic evaluators**, each independently unit tested with
  hand-computed expected values: schema/required-field/type/enum
  correctness, factual/numeric correctness (exact, normalized-string,
  tolerance, date), retrieval metrics (Recall@K, Precision@K, MRR, nDCG),
  three-part citation grounding (exists / relevant / lexically supports),
  abstention correctness (never invents a value when evidence is missing),
  conflict detection (flags disagreement across sources), and missing-field
  correctness.
- **Test runner** (`app/runner/engine.py`) that executes a dataset version
  against a real adapter, persists every execution with explicit statuses
  (`passed` / `failed` / `unevaluated` / `execution_error` / `cancelled`),
  and never counts an unsupported or inapplicable evaluator as a pass.
- **Regression engine** (`app/runner/regression.py`): compares two saved
  runs test-case by test-case (new/resolved/unchanged failures, newly
  passed, non-comparable, category-level breakdown, critical-failure
  tracking) plus a configurable release gate that blocks on critical
  failures regardless of average score.
- **A real FastAPI app**, organized as routers (`app/api/`): projects and
  integrations (create + validate), runs and regression comparison, and
  **dataset/test-case management** -- evaluation packs, datasets, dataset
  version snapshots, test case CRUD with search/filter (category, severity,
  tag, free-text), content-hash-based duplicate detection, actionable
  validation errors, and JSON/CSV bulk import + export (round-trip tested
  both ways). All backed by the database, no hardcoded responses.
- **Report export**: `GET /runs/{run_id}/report?format=json|markdown` --
  run metadata, metrics with coverage and accuracy kept as separate
  denominators, failures with evaluator detail, unavailable-evaluation
  coverage gaps (grouped by evaluator+reason in Markdown), an automatic
  regression section when the run has a baseline, and a "known
  limitations" list read off the run's own real evaluator output (not a
  fixed boilerplate list). A real sample pulled from an actual run is
  checked in at `docs/sample_reports/`.
- **Document fixture upload with OCR fallback**:
  `POST /projects/{project_id}/documents` accepts PDF/TXT/JSON, validates
  type and size, and for PDFs tries native text extraction (`pypdf`)
  first. If that looks like a scanned/image PDF (very little text per
  page) and `MISTRAL_API_KEY` is set, it falls back to Mistral's OCR API
  (the real 3-call contract -- upload, get a signed URL, call OCR --
  verified against docs.mistral.ai, not guessed; see `docs/ocr.md`). If
  OCR isn't configured or itself fails, the document is still saved but
  marked `extraction_status: "partial"` with an explicit reason --
  never silently reported as fully read when it wasn't. Verified live
  with a real hand-built PDF (not just mocked): real native extraction,
  real 400/413 validation errors, real partial-status fallback path.
- **95 passing automated tests** (`backend/tests/`), including true
  end-to-end runs through both the mock adapter and the CovenAce file
  adapter, full API-level tests via FastAPI's TestClient, and a
  persistence test that reopens the SQLite file in a fresh process to
  confirm data survives a restart.

## What's NOT yet implemented

- 4 of the 12 originally planned frontend pages remain: a dedicated
  test-case JSON/CSV editor UI (the API supports it; there's no dedicated
  editor page yet, just create-one-at-a-time), an evaluation
  methodology/config page, and a report-download-browser page (the API +
  a run-detail link already exist, see Report export above). What exists:
  dashboard, projects & integrations, document collection (upload + browse
  extracted pages, including partial-extraction notes), dataset/test-case
  browsing + creation, run creation, run detail + trace viewer, regression
  compare.
- The live CovenAce Python/workflow adapter -- blocked on the entry-point
  details listed in docs/adapter_guide.md. The CovenAce evaluation pack
  itself exists and is tested, but only in file/batch mode.
- LLM-as-judge evaluator (deliberately deferred; deterministic evaluators
  are sufficient for the free local demo per the project requirements).

## Setup

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; use .venv\Scripts\activate.bat on cmd.exe
pip install -r requirements.txt
cp .env.example .env               # edit if you need non-default settings
```

## Run the automated tests

```bash
cd backend
source .venv/Scripts/activate
python -m pytest -q
```

Expected: `95 passed`.

## Run the app locally

```bash
cd backend
source .venv/Scripts/activate
PYTHONPATH=. python scripts/seed_mock_demo.py      # mock pack: real run + a controlled regression
PYTHONPATH=. python scripts/seed_covenace_demo.py   # CovenAce pack: real synthetic-case run (file adapter)
python -m uvicorn app.main:app --port 8731
```

Then, in another terminal:

```bash
curl http://127.0.0.1:8731/health
curl http://127.0.0.1:8731/projects
```

The seed script also runs a second "regressed configuration" integration
against the same dataset and prints a real regression summary and
release-gate verdict -- this is the generic engine proving itself on the
mock target before any domain-specific (CovenAce) work begins.

Browse and call every endpoint interactively at
**http://127.0.0.1:8731/docs** (FastAPI's auto-generated Swagger UI) --
no code needed.

## Managing datasets and test cases via the API

```
POST   /evaluation-packs                              create a pack
GET    /evaluation-packs
POST   /projects/{project_id}/datasets                 create a dataset
GET    /projects/{project_id}/datasets
POST   /datasets/{dataset_id}/test-cases               create a test case (validates, rejects exact-content duplicates)
GET    /datasets/{dataset_id}/test-cases               ?category=&severity=&tag=&q=&status=
GET    /test-cases/{test_case_id}
PUT    /test-cases/{test_case_id}                      bumps version + content_hash
DELETE /test-cases/{test_case_id}                      soft delete (archived, not removed)
POST   /datasets/{dataset_id}/test-cases/import        bulk JSON import -> {created, skipped_duplicates, errors}
POST   /datasets/{dataset_id}/test-cases/import-csv    multipart file upload, same report shape
GET    /datasets/{dataset_id}/test-cases/export        ?format=json|csv
POST   /datasets/{dataset_id}/versions                 immutable snapshot of current active test cases
GET    /datasets/{dataset_id}/versions
GET    /runs/{run_id}/report                           ?format=json|markdown
POST   /projects/{project_id}/documents                 multipart upload (pdf/txt/json), see docs/ocr.md
GET    /projects/{project_id}/documents
GET    /documents/{document_id}
```

## Frontend

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api/* to the backend on :8731
```

React + Vite + JavaScript (not TypeScript) + Tailwind v4, no mocked data --
every page calls the real backend API above. Pages: Dashboard (real
pass-rate/coverage/critical-failure stats, denominators kept separate per
the project's own requirement not to conflate coverage with accuracy),
Projects & Integrations (create, validate, add integrations/datasets/packs
inline), Document Collection (upload, browse extracted pages, see
partial-extraction reasons), Dataset detail (test-case search/filter,
create, JSON/CSV import+export), Run creation, Run detail (expandable
trace viewer showing real trace events and evaluator results per
execution, plus report download links), Regression Compare.

**Known limitation -- not verified in a live browser in this session.**
`npm run build` succeeds (confirms no import/syntax/type errors across all
36 modules) and the code was reviewed line-by-line, but the dev server
could not actually be loaded in a browser here: this machine deterministically
hits a Windows `EBUSY: resource busy or locked` error renaming Vite's
dependency-optimizer temp directory, in every location tried (project
folder and OS temp folder) and with several Vite config workarounds
attempted -- the signature matches antivirus real-time scanning locking a
freshly-created folder. Fixing it needs a Windows Defender exclusion for
the project (or frontend/node_modules) folder, which wasn't made without
explicit approval since it's a security-relevant system change. If you hit
the same error running `npm run dev` yourself: add that exclusion, or try
on a machine without the same antivirus policy, then let me know and I'll
do the actual browser walkthrough (click through each page, verify the
trace viewer expands, verify create/import/export round-trip in the UI)
that this README currently cannot claim.

Round-trip tested both ways (export then re-import reproduces the same
test cases) in `backend/tests/test_dataset_and_test_case_api.py`.

## Database reset

SQLite file lives at `backend/data/trusttrace.db`. To reset: stop the
server, delete that file, and re-run `init_db()` (happens automatically on
app startup) or the seed script.
