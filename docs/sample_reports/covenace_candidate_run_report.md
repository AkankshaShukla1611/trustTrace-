# TrustTrace Run Report

Generated: 2026-10-20T14:41:50.305504+00:00

## Run
- Run ID: `6d264361-5956-43ad-9d0a-b866da5cefc5`
- Label: Output Year memo (candidate)
- Project: CovenAce Demo (synthetic Whole Eagle) (`3556734e-cb0d-46d5-93ed-acd87d51044c`)
- Integration: File adapter (output_year variant) -- adapter type `file`
- Dataset: Whole Eagle FY24 review dataset version 1 (`f8530dae-6814-4bb8-a423-8185c400f539`)
- Mode: full_dataset -- Status: completed
- Started: 2026-10-20T12:11:04.322163 -- Finished: 2026-10-20T12:11:04.338498
- Baseline run for comparison: `14fdc20c-5399-434e-9107-c28e97b3381e`

## Metrics
- Total executions: 7
- Passed: 2 | Failed: 5 | Unevaluated: 0 | Execution errors: 0 | Cancelled: 0
- Pass rate (of evaluated only): 28.6% -- excludes unevaluated cases
- Evaluation coverage: 100.0% -- coverage, not accuracy

### By category
| Category | Passed | Failed | Unevaluated | Execution error |
|---|---|---|---|---|
| extraction | 1 | 1 | 0 | 0 |
| citation | 0 | 1 | 0 | 0 |
| conflict | 0 | 1 | 0 | 0 |
| missing_info | 1 | 1 | 0 | 0 |
| hitl | 0 | 1 | 0 | 0 |

### By severity
| Severity | Passed | Failed | Unevaluated | Execution error |
|---|---|---|---|---|
| medium | 1 | 0 | 0 | 0 |
| high | 1 | 3 | 0 | 0 |
| critical | 0 | 2 | 0 | 0 |

## Failures (5)
- **FY2024 DSCR cited in memo does not match the covenant-testing workbook** (extraction, severity high) -- failed
  - factual_correctness [fail]: 'fy2024_dscr' expected 2.64, got 3.26
- **FY2024 DSCR claim cites the wrong source workbook** (citation, severity high) -- failed
  - citation_grounding [fail]: one or more citations do not point to a labeled relevant passage
- **Conflicting FY2024 DSCR across source workbooks is not flagged** (conflict, severity critical) -- failed
  - conflict_detection [fail]: did not flag a conflict for: fy2024_dscr
- **Controlled test: inventing the undocumented covenant threshold must fail** (missing_info, severity high) -- failed
  - missing_field [fail]: invented a value for field(s) expected to be reported missing: contractual_min_dscr_covenant
- **Credit memo has no unresolved human-in-the-loop review flags** (hitl, severity critical) -- failed
  - hitl_gate [fail]: 8 unresolved human-in-the-loop item(s) remain: ['HITL - Confirm if there is any change in the management from last year', 'HITL - RM: please confirm the reason for the net sales increase', 'HITL - RM: please confirm the reason for the SG&A increase', 'HITL - historical performance trend is based on only FY23 and FY24', 'HITL - RM: please confirm the reason for the working capital increase', "HITL - risks & mitigants carried from last year's memo; update per latest scenario (Key Risks #1)", "HITL - risks & mitigants carried from last year's memo; update per latest scenario (Key Risks #2)", 'HITL - PD and LGD grade not explicitly supported by source documents; human confirmation required']

## Unavailable evaluations (48)
Evaluators with nothing applicable to check -- not counted toward pass or fail. Grouped by evaluator and reason (full per-case detail is in the JSON report).
- **abstention** (7x): test case behavior_type is not 'abstain_expected'
- **retrieval_metrics** (7x): test case declares no labeled relevant_passage_ids
- **schema_correctness** (7x): test case declares no schema_correctness config
- **conflict_detection** (6x): test case behavior_type is not 'conflict_flag_expected'
- **hitl_gate** (6x): test case declares no hitl_gate config
- **citation_grounding** (5x): no citations to evaluate and none were expected
- **factual_correctness** (5x): test case behavior_type is not 'exact_fields'
- **missing_field** (5x): test case declares no expected_missing_fields

## Regression vs. baseline
- New failures: 1
- Critical failures: 1
- Resolved failures: 0
- Newly passed: 0
- Unchanged failures: 4
- Non-comparable (dataset changed): 0
- Integration config changed: True

## Known limitations
- 7 of 7 execution(s) with known execution-mode metadata ran in file/batch mode and could not independently test live target execution.
- support check is lexical-overlap only, not semantic entailment
