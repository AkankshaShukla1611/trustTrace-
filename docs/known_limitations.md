# Known limitations and outstanding integration requirements

A single consolidated list -- everything elsewhere in this repo that says
"not yet", "blocked", "deferred", or "partial", gathered in one place so
nothing is implied to be finished that isn't.

## Blocked on external access

- **Live CovenAce adapter.** The CovenAce evaluation pack exists and is
  tested (`backend/app/evaluation_packs/covenace_pack/`), but only
  through the `file` adapter -- it evaluates pre-supplied output against
  real source documents, and explicitly cannot test CovenAce's actual
  execution. A real "Covenace-appraisal-static-clean" instance exists on
  this machine but is confirmed to be the static variant, not the live
  one TrustTrace would need to call -- not inspected, per instruction.
  Exactly what's needed to build the live `python` adapter is listed in
  `docs/adapter_guide.md` (entry point, input/output shape, HITL
  representation, a safe/non-production mode, error behavior, and
  whether per-stage output is inspectable).
- **Live ANA adapter.** Not started. ANA (Anaptyss's control-assurance
  product) was researched only via its public marketing page -- no
  adapter, pack, or fixtures exist for it.

## Partial by design, not by oversight

- **LLM-as-judge evaluator is built, but only verified without a real key.**
  `app/evaluators/llm_judge.py` is wired in (9th evaluator, opt-in per
  test case, requires `ANTHROPIC_API_KEY`), its exact request/response
  contract is checked against current Claude API docs, and 10 tests cover
  opt-in gating, verdict mapping, error handling, and the full runner
  integration -- all with the Anthropic client mocked. It has never been
  exercised against a real Claude response, because no API key has been
  supplied in this environment. If you add a key, a disputed/inconclusive
  verdict surfaces as `needs_review`, never silently as a pass.

- **File/batch adapter mode** (used for the whole CovenAce pack today)
  can only evaluate supplied output and evidence -- it is structurally
  incapable of testing a target's live execution, and every report
  generated from a file-mode run says so explicitly in its "known
  limitations" section (derived from real `config_metadata`, not a
  canned disclaimer).
- **Citation "support" checks** are deterministic lexical-overlap
  heuristics, not semantic entailment. A citation can overlap in wording
  without actually supporting a claim, or genuinely support a claim
  using different words that don't overlap. Every `citation_grounding`
  result reports this limitation inline.
- **OCR fallback for scanned PDFs** only engages if `MISTRAL_API_KEY` is
  configured; without it, a scanned PDF is still accepted but marked
  `extraction_status: "partial"` with an explicit reason. No other OCR
  provider is wired in. Tables/layout within OCR'd text are treated as
  plain markdown text, not structured data.
- **HTTP adapter** is implemented and unit-tested (config validation,
  request/response mapping, secret-env-var resolution, timeout/error
  handling) but has not been demonstrated against a real live HTTP
  target end-to-end in this project -- only mock and file adapters have
  a full demo run. The adapter contract itself is exercised the same way
  regardless, but there's no "real server" demo script for it yet.
- **Regression comparison** only compares two runs built from the same
  generic engine; it has no concept of statistical significance or
  sample-size warnings for small datasets (all current demo datasets are
  4-7 test cases).

## Frontend

- **All 12 originally-planned pages exist** (dashboard, projects &
  integrations, document collection, dataset/test-case management --
  including editing an existing case, not just create-then-archive --
  run creation, run detail/trace viewer, regression compare, reports
  browser with inline preview, evaluation methodology), each verified
  with a real headless-browser render against real backend data.
- **`npm run dev` does not work on this development machine** -- a
  Windows file-lock (`EBUSY`) in Vite's dependency-optimizer step,
  matching an antivirus real-time-scan signature, reproduced across every
  cache location and config workaround tried. The real fix (a Windows
  Defender exclusion) was not applied without explicit approval, since
  it's a security-relevant system change.
  **Workaround, verified working**: `npm run build && npx vite preview`
  serves the production bundle as static files, which skips the failing
  step entirely. This was verified with an actual headless-browser
  render against real backend data (not just an HTTP 200 check) --
  every page loads real content with zero console errors, including the
  trace viewer genuinely expanding real evaluator results. See the
  README's "Known limitation" section under Frontend for exact commands.

## What is NOT a limitation (explicitly verified, not assumed)

To avoid these being mistaken for open questions:

- All 96 backend tests pass, including true end-to-end runs through the
  mock and CovenAce (file) adapters, full API-level tests, and a
  persistence check that reopens the SQLite file in a fresh process.
- The Mistral OCR integration's exact 3-call contract (upload file, get
  signed URL, call OCR) is verified against docs.mistral.ai directly, not
  assumed, and tested via a fake HTTP client that checks the exact call
  sequence and auth header -- it works correctly whether or not a real
  key is ever supplied.
- Every CovenAce test case's expected value is cited to a real source
  document/page in `backend/app/evaluation_packs/covenace_pack/README.md`
  -- including two genuine findings (a cross-workbook DSCR discrepancy,
  and 8 real unresolved HITL markers in one memo vs. zero in another)
  that were found while reading the files, not injected to make the demo
  look good.
