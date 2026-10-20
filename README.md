# TrustTrace

A generic AI evaluation, testing, and regression platform. TrustTrace tests
RAG apps, LLM document-processing workflows, extraction/classification
pipelines, and tool-using agents through one reusable core, pluggable
adapters, and per-application evaluation packs.

**Status: Phase 1-2 of the build (generic core) is implemented and tested.**
Frontend, the CovenAce evaluation pack, and the API surface for dataset/test
case management are not yet built -- see "What's implemented" below for the
exact boundary.

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
- **A real FastAPI app** (`app/main.py`) exposing projects, integrations
  (create + validate), runs, and regression comparison -- all backed by the
  above, no hardcoded responses.
- **42 passing automated tests** (`backend/tests/`), including a true
  end-to-end run through the mock adapter and a persistence test that
  reopens the SQLite file in a fresh process to confirm data survives a
  restart.

## What's NOT yet implemented

- React/Vite frontend (all 12 planned pages).
- Dataset/test-case management API + JSON/CSV import-export.
- Document fixture upload/OCR pipeline.
- The CovenAce evaluation pack and its Python/workflow adapter (blocked on
  the CovenAce entry-point details listed in docs/adapter_guide.md).
- LLM-as-judge evaluator (deliberately deferred; deterministic evaluators
  are sufficient for the free local demo per the project requirements).
- Report export (JSON/Markdown).

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

Expected: `42 passed`.

## Run the app locally

```bash
cd backend
source .venv/Scripts/activate
PYTHONPATH=. python scripts/seed_mock_demo.py   # creates backend/data/trusttrace.db with a real run
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

## Database reset

SQLite file lives at `backend/data/trusttrace.db`. To reset: stop the
server, delete that file, and re-run `init_db()` (happens automatically on
app startup) or the seed script.
