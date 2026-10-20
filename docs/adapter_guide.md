# Adding a new target application to TrustTrace

Adding a project should never require touching the test runner, the
database schema, or the evaluators. It requires:

1. Pick an adapter type: `mock`, `http`, `python`, or `file`
   (`backend/app/adapters/`). Write a new one only if none of these fit --
   the contract is small (see `app/adapters/base.py`).
2. Create a `Project` and an `Integration` row (`adapter_type` + `config`).
3. Create (or reuse) an `EvaluationPack` and a `Dataset` of `TestCase` rows
   that describe what correct behavior looks like for this application.
4. Create a `DatasetVersion` snapshot and call
   `app.runner.engine.run_dataset_version(...)`.

Nothing else changes. The runner, the seven evaluators, and the regression
engine work against any adapter and any evaluation pack unmodified.

## The adapter contract

Every adapter implements `app.adapters.base.BaseAdapter`:

```python
class BaseAdapter(ABC):
    def validate_config(self) -> ValidationResult: ...
    def get_capabilities(self) -> AdapterCapabilities: ...
    def execute(self, input_payload: dict, *, timeout_seconds: float = 30.0) -> AdapterExecutionResult: ...
    def cleanup(self) -> None: ...
```

`AdapterCapabilities` is a set of booleans (`intermediate_traces`,
`retrieved_passages`, `tool_calls`, `config_metadata`, ...). **Declare a
capability `False` if you can't actually provide it -- never fabricate a
trace, passage, or tool call to look more complete.** The UI (once built)
and the evaluators both read this to decide what to show/check.

`AdapterExecutionResult` carries back: `status` (`ok`/`error`/`timeout`),
`output`, `trace_events` (ordered, free-form `stage_name` + `payload`),
`retrieved_passages`, `tool_calls`, `config_metadata`, and
`error_category`/`error_detail` on failure.

## Worked example: the mock adapter

`app/adapters/mock_adapter.py` wraps `app/example_app/engine.py` (a tiny
deterministic lexical-search + regex-extraction engine -- Module D's
"example target application", not part of the core). It declares
`retrieved_passages=True` and `tool_calls=False` because it genuinely
returns the former and never has the latter. Read it end to end as the
reference implementation before writing a new adapter.

## Choosing an adapter type for a new project

- **HTTP adapter**: the target exposes a request/response API. Configure
  `base_url`, `endpoint`, `request_mapping` (dict: your field -> input
  payload path), `response_mapping` (dict: core field -> response path),
  and `auth.secret_env_var` (never a plaintext secret in `config`).
- **Python adapter**: you can install/import the target as a Python module
  in TrustTrace's own environment. Configure `module_path` + `function_name`
  of an already-approved function that accepts the input payload and
  returns a dict. This is a deployment-time wiring decision, not a
  mechanism for running arbitrary code supplied at request time -- treat
  integration config as operator-only, not end-user-editable.
- **File/batch adapter**: you can't invoke the target live, only get
  exported outputs. The test case's `input_payload` must carry
  `supplied_output` (and optionally `supplied_evidence`) directly; the
  adapter just reads it back. This mode is explicitly incapable of testing
  live execution -- never present it as a live integration test.

## What's needed to connect CovenAce (blocked, not yet done)

CovenAce will use the Python adapter. To write `covenace_wrapper.py` (the
thin module the adapter imports) we need, from whoever owns the CovenAce
codebase:

1. The actual entry point: module/function or class to call per document,
   and whether it's importable in-process or must run as a separate
   service.
2. Input shape (file path/bytes, loan/borrower ID, config) and output shape
   (extracted fields, confidence, page/section citations, reconciliation
   diffs) -- at least one real or representative sample.
3. How "pending human review" vs. "approved" is represented in its data, so
   the HITL gate can be checked.
4. A safe/non-production mode so a TrustTrace run can never write to a real
   loan system or trigger a real notification.
5. What it raises/returns on bad input, missing file, or timeout.
6. Whether per-stage output (ingest/extract/reconcile/review/analyze) is
   inspectable, or only the final result.

Until these are provided, the CovenAce evaluation pack will be built and
tested entirely through the `file` adapter against synthetic fixtures, with
the integration gap stated explicitly rather than assumed.
