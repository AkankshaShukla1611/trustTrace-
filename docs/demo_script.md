# TrustTrace demo script

A walkthrough showing: a passing test, a controlled failure, trace
investigation, and a regression comparison -- all against real, persisted
data from an actual run, not a scripted fake. Every command below was
run for real while writing this script; the run IDs shown are from that
run and will be different (but structurally identical) after you reset
the database and re-seed.

## 0. Setup

```bash
cd backend
source .venv/Scripts/activate
rm -f data/trusttrace.db
PYTHONPATH=. python scripts/seed_mock_demo.py
PYTHONPATH=. python scripts/seed_covenace_demo.py
python -m uvicorn app.main:app --port 8731 &
```

In another terminal, for the UI (see README's "Known limitation" if
`npm run dev` fails on Windows):

```bash
cd frontend
npm install
npm run build && npx vite preview --port 4173
```

Open **http://localhost:4173**.

## 1. A passing test

The CovenAce pack's `net_sales_extraction_matches_source` case compares a
value the credit memo states ($278.9M) against the real source PDF's
figure ($278,884k), within a rounding tolerance:

```bash
curl -s http://127.0.0.1:8731/runs | python -m json.tool   # grab a CovenAce run id, e.g. the "baseline" one
curl -s "http://127.0.0.1:8731/runs/<run_id>/report?format=markdown" | grep -A2 "Net sales"
```

That `grep` on the report comes back empty for this case precisely
because it *passed* -- the Markdown report's Failures section only lists
failing cases, by design. To see the passing result directly: **Runs →
(a CovenAce run) → click the "Net sales extraction..." row** in the UI.
The `factual_correctness` evaluator shows `status: pass`, `score: 1.0`,
reason `"all 1 field(s) matched"`.

## 2. A controlled failure, with a real root cause

The same run's `fy2024_dscr_incorrect_value` case fails --
`factual_correctness` reports:

> 'fy2024_dscr' expected 2.64, got 3.26

This isn't a scripted failure -- it's a genuine discrepancy found while
building the CovenAce pack: `Cash Flow Coverage Analysis_Whole Eagle.xlsx`
and `Covenant Calculations_Whole Eagle.xlsx` compute FY2024 DSCR
differently for the same period (see
`backend/app/evaluation_packs/covenace_pack/README.md` for the full
citation). The memo cites the former; the covenant-testing workbook (the
latter) is treated as authoritative here.

## 3. Trace investigation

In the UI, click any execution row to expand it. For the HITL-gate case,
the "Evaluator results" panel shows the real reason text:

```
hitl_gate [fail]: 8 unresolved human-in-the-loop item(s) remain: [...]
```

Those 8 items are literal `HITL`/`HILT` markers found in the real credit
memo text (e.g. "HITL - PD and LGD grade not explicitly supported by
source documents; human confirmation required"), not fabricated for the
demo -- verifiable by opening the original `.docx` and searching for
"HITL".

Via the API directly:

```bash
curl -s "http://127.0.0.1:8731/runs/<run_id>" | python -m json.tool
```

gives the full per-execution trace events, retrieved passages, and
evaluator results for every test case in the run.

## 4. Regression comparison

The CovenAce pack's candidate run (Output Year memo) is a real regression
against its baseline run (Prior Year memo) -- the newer memo has 8
unresolved HITL markers, the prior one has zero:

```bash
curl -s -X POST http://127.0.0.1:8731/regression/compare \
  -H "Content-Type: application/json" \
  -d '{"baseline_run_id": "<baseline_run_id>", "candidate_run_id": "<candidate_run_id>"}' \
  | python -m json.tool
```

Expect `new_failures` and `critical_failures` to each contain exactly one
test case ID (the HITL-gate case), `resolved_failures`/`newly_passed`
empty, and `unchanged_failures` containing the 4 cases that fail in both
runs for unrelated reasons (the real DSCR/conflict/citation findings from
step 2). In the UI: **Regression Compare → pick both runs → Compare**.

## 5. Report export

```bash
curl -s "http://127.0.0.1:8731/runs/<candidate_run_id>/report?format=markdown"
```

or click **"Download report (Markdown)"** on that run's detail page. A
real example of this output is checked in at
`docs/sample_reports/covenace_candidate_run_report.md`.

## 6. Proving it's not hardcoded (optional, for a skeptical audience)

```bash
cd backend && source .venv/Scripts/activate && python -c "
from app.evaluators.base import EvaluationContext
from app.evaluators.factual_correctness import FactualCorrectnessEvaluator

e = FactualCorrectnessEvaluator()
ctx = EvaluationContext(
    test_case={'behavior_type': 'exact_fields', 'expected_output': {'x': 100}, 'evaluator_config': {}},
    actual_output={'x': 999},
)
print(e.evaluate(ctx).status, e.evaluate(ctx).reason)
"
```

Change the `999` to `100` and re-run -- the verdict flips from `fail` to
`pass` with the exact same code, because the evaluator genuinely computes
its answer from the input rather than returning a fixed result.
