# TrustTrace

A generic AI evaluation, testing, and regression platform. TrustTrace tests
RAG apps, LLM document-processing workflows, extraction/classification
pipelines, and tool-using agents through one reusable core, pluggable
adapters, and per-application evaluation packs.

**Status:** backend (generic core, 2 evaluation packs, full API) is
implemented and tested. The frontend (all 12 planned pages) is verified
end to end with a real headless browser rendering real data -- but only in
production-preview mode (`npm run preview`), not `npm run dev`; see "Known
limitation" below for why. See "What's implemented" for the exact boundary.

## Architecture

```
Layer A  Generic core        project/integration mgmt, test runner,
                              evaluation engine, persistence, regression
Layer B  Adapters             mock | http | python | file  (app/adapters/)
Layer C  Evaluation packs     per-application test cases + domain rules
                              (app/evaluation_packs/, DB-backed EvaluationPack)
```

See [docs/architecture.md](docs/architecture.md) for the full data model,
[docs/adapter_guide.md](docs/adapter_guide.md) for how to connect a new
target application without touching the core, [docs/demo_script.md](docs/demo_script.md)
for a guided walkthrough (passing test → controlled failure → trace
investigation → regression comparison), and
[docs/known_limitations.md](docs/known_limitations.md) for a single
consolidated list of everything not yet done, blocked, or partial.

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
- **Eight deterministic evaluators**, each independently unit tested with
  hand-computed expected values: schema/required-field/type/enum
  correctness, factual/numeric correctness (exact, normalized-string,
  tolerance, date), retrieval metrics (Recall@K, Precision@K, MRR, nDCG),
  three-part citation grounding (exists / relevant / lexically supports),
  abstention correctness (never invents a value when evidence is missing),
  conflict detection (flags disagreement across sources), missing-field
  correctness, and an HITL gate (no unresolved human-review flags before
  output is treated as finalized). Plus a 9th, optional LLM-as-judge
  evaluator -- see below.
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
- **Optional LLM-as-judge evaluator** (`app/evaluators/llm_judge.py`):
  9th evaluator, strictly opt-in -- unavailable unless a test case sets
  `evaluator_config["llm_judge"]` *and* `ANTHROPIC_API_KEY` is configured,
  so the free local demo never needs it (8 deterministic evaluators are
  the whole demo). Uses Claude's `output_config.format` / `json_schema`
  structured-output feature for a guaranteed-parseable verdict
  (`pass`/`fail`/`inconclusive`), with the real request/response contract
  checked against current docs before writing the code -- the same
  discipline as the Mistral OCR integration. An `inconclusive` verdict is
  never silently counted as a pass: it rolls the execution up to a new
  `needs_review` status, surfaced on the dashboard and in a dedicated
  report section, so a disputed result reaches a human instead of
  disappearing into "passed." `GET /evaluators` marks it
  `deterministic: false` so the UI never conflates a model's opinion with
  a deterministic fact.
- **112 passing automated tests** (`backend/tests/`), including true
  end-to-end runs through the mock adapter, the CovenAce file adapter,
  and the LLM judge (Anthropic client mocked -- no real key needed to
  verify the integration wires together correctly), full API-level tests
  via FastAPI's TestClient, and a persistence test that reopens the
  SQLite file in a fresh process to confirm data survives a restart.

## What's NOT yet implemented

- All 12 originally planned frontend pages now exist: dashboard, projects
  & integrations, document collection, dataset/test-case management
  (create, search/filter, **edit existing cases** -- not just
  create-then-archive, JSON/CSV import+export), run creation, run detail
  + trace viewer, regression compare, reports (browse + inline preview +
  download every run's report, not just a link on its own run page), and
  evaluation methodology.
- The live CovenAce Python/workflow adapter -- blocked on the entry-point
  details listed in docs/adapter_guide.md. The CovenAce evaluation pack
  itself exists and is tested, but only in file/batch mode.

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

Expected: `112 passed`.

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
GET    /evaluators                                     descriptions pulled live from each evaluator's docstring
```

## Frontend

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 -- hot reload; see the known limitation below first on Windows
```

If `npm run dev` hits a Windows `EBUSY` error (see "Known limitation"
below), use this instead -- no hot reload, but otherwise the full real app:

```bash
npm run build
npx vite preview --port 4173    # http://localhost:4173
```

React + Vite + JavaScript (not TypeScript) + Tailwind v4, no mocked data --
every page calls the real backend API above. Pages: Dashboard (real
pass-rate/coverage/critical-failure stats, denominators kept separate per
the project's own requirement not to conflate coverage with accuracy),
Projects & Integrations (create, validate, add integrations/datasets/packs
inline), Document Collection (upload, browse extracted pages, see
partial-extraction reasons), Dataset detail (test-case search/filter,
create, **edit**, JSON/CSV import+export), Run creation, Run detail
(expandable trace viewer showing real trace events and evaluator results
per execution), Regression Compare, Reports (browse every run, preview a
report's Markdown inline, download JSON/Markdown), Evaluation Methodology
(evaluator descriptions + coverage-vs-accuracy explanation).

**Known limitation -- `npm run dev` doesn't work in this environment,
use `npm run preview` instead.** `npm run dev` hits a Windows `EBUSY:
resource busy or locked` error renaming Vite's dependency-optimizer temp
directory, in every location and config workaround tried -- the signature
matches antivirus real-time scanning locking a freshly-created folder.
The real fix is a Windows Defender exclusion for the project folder,
which wasn't made without explicit approval since it's a security-relevant
system change.

The workaround that works: `npm run build && npx vite preview --port 4173`
serves the production bundle as static files, which skips the dependency
optimizer entirely (no dev-mode hot-reload, but otherwise the full real
app, proxying `/api/*` to the backend the same way). This was verified
with an actual headless-browser render (Playwright) against real backend
data -- every page above loaded real content with zero console errors,
including the Run Detail trace viewer genuinely expanding to show real
`actual_input`/`actual_output`/evaluator results. If you fix the Defender
exclusion and want `npm run dev`'s hot reload back, that's a config
revert, not a code change.

Round-trip tested both ways (export then re-import reproduces the same
test cases) in `backend/tests/test_dataset_and_test_case_api.py`.

## Database reset

SQLite file lives at `backend/data/trusttrace.db`. To reset: stop the
server, delete that file, and re-run `init_db()` (happens automatically on
app startup) or the seed script.
