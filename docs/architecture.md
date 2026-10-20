# TrustTrace architecture

## Three layers

**Layer A -- generic core** (`backend/app/`): data models, the test runner,
the deterministic evaluators, regression comparison, and (eventually) the
API/dashboard. Nothing here branches on which application is being tested.
It reads `EvaluationPack.rules_config` and `TestCase.evaluator_config` as
opaque data -- it never contains an `if project == "covenace"` anywhere.

**Layer B -- adapters** (`backend/app/adapters/`): the only code that knows
how to talk to a specific *kind* of target (an HTTP API, a local Python
function, etc). An adapter never evaluates correctness -- it only reports
what actually happened.

**Layer C -- evaluation packs**: an `EvaluationPack` row plus a `Dataset` of
`TestCase` rows is a pack. `app/evaluation_packs/mock_pack/` holds the mock
pack's fixtures; a second pack (e.g. CovenAce) lives alongside it with its
own fixtures and is loaded through the same generic `TestCase`/`Dataset`
tables -- no schema changes required to add one.

## Data model

```
Project ──┬── Integration (adapter_type, config, capabilities, status)
          └── Dataset ── DatasetVersion (immutable test_case_snapshot)
                └── TestCase (behavior_type, expected_output/evidence,
                               relevant_passage_ids, evaluator_config)

Run (project, integration, dataset_version) ── TestExecution*
    TestExecution ── TraceEvent*        (ordered pipeline stages)
    TestExecution ── EvaluatorResult*   (one per evaluator that ran)

RegressionComparison (baseline_run, candidate_run, summary)
```

Key design choices and why:

- **`TestCase.behavior_type`** is one of `exact_fields`, `free_text`,
  `abstain_expected`, `conflict_flag_expected`. This is what lets a test
  case express "the answer must equal X" *or* "the correct behavior is to
  abstain" without forcing everything into an exact-match comparison.
- **`TraceEvent.stage_name`** is a free string, not a fixed enum, because
  different target applications have different pipelines (CovenAce:
  ingest/extract/reconcile/review/analyze/monitor; ANA: walkthrough/test of
  design/test of effectiveness/risk gaps/reporting). The core never assumes
  a fixed stage list.
- **`DatasetVersion.test_case_snapshot`** freezes which test case IDs (and
  a content hash) belonged to a dataset at run time, so a run started today
  stays reproducible even if test cases are edited tomorrow.
- **`EvaluatorResult.status` includes `unavailable`**, distinct from `pass`
  and `fail`. An evaluator that has nothing to check (no labeled evidence,
  no schema declared, wrong behavior_type for this evaluator) reports
  `unavailable`, and `compute_execution_status()`
  (`app/evaluators/__init__.py`) never counts that as a pass. An execution
  with zero applicable evaluators is `unevaluated`, not `passed`.

## Execution flow (`app/runner/engine.py`)

1. Resolve the `Integration`'s adapter class from the registry
   (`app/adapters/registry.py`).
2. For each `TestCase` in the dataset version's snapshot: call
   `adapter.execute(input_payload)`, persist the raw result (output, trace
   events, retrieved passages, tool calls, error category) as a
   `TestExecution` -- before any evaluation happens, so raw output and
   evaluation reasoning are never conflated.
3. If the adapter reported an error/timeout, the execution is marked
   `execution_error` and evaluation is skipped (a timeout is not the same
   thing as a wrong answer).
4. Otherwise, every evaluator in `DETERMINISTIC_EVALUATORS` runs against
   the same `EvaluationContext`; each decides independently whether it's
   applicable. The execution's overall status is rolled up from those
   results.

## Regression and release gates (`app/runner/regression.py`)

`compare_runs()` matches executions by `test_case_id` across two runs and
buckets them into new/resolved/unchanged failures, newly passed, and
non-comparable (present in only one run). `evaluate_release_gate()` is a
small, configurable rule evaluator -- by default it blocks release if any
*critical*-severity test case regressed, regardless of the aggregate pass
rate, so a good average score can never hide a critical regression.

## What's deliberately NOT built

- No arbitrary/dynamic plugin execution engine. Adapters and evaluators are
  plain Python classes wired through a small registry; adding one means
  writing a class and registering it, not configuring a plugin DSL.
- No LLM-as-judge by default -- every evaluator currently shipped is a pure
  deterministic function, so the demo needs no API key and no network call.
