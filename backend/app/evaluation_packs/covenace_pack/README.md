# CovenAce evaluation pack

## Status: file/batch mode only -- live CovenAce integration is blocked

TrustTrace cannot yet call the real CovenAce workflow. The adapter guide
(`docs/adapter_guide.md`) lists exactly what's needed from the CovenAce
codebase to build the `python` adapter. Until that's provided, this pack
runs through the `file` adapter: it evaluates outputs that were already
produced (here, hand-transcribed from a real credit memo's own stated
figures) against real source documents, and is explicitly incapable of
testing CovenAce's actual internal execution.

## Data provenance

The fixtures in `fixtures/` are extracted text from a confirmed **synthetic
demo case** ("Whole Eagle Distributors Inc.", a fictitious PA beer
distributor) -- confirmed both by the data owner and by the source PDF's
own Note 1 ("The accompanying financial statements are fictitious") and
Note 8 ("For this fictitious presentation..."). No real customer data is
used. Source files (not checked into this repo) live at:

```
new C&I inputs/
  WholeEagle FY24.pdf                          -> fixtures/wholeeagle_fy24_pdf.json
  Cash Flow Coverage Analysis_Whole Eagle.xlsx  -> fixtures/cashflow_coverage_whole_eagle.json
  Covenant Calculations_Whole Eagle.xlsx        -> fixtures/covenant_calc_whole_eagle.json
  Whole Eagle Credit Memo_Prior Year Memo.docx  -> referenced by quote in scripts/seed_covenace_demo.py
  Whole Eagle Credit Memo_Output Year Memo.docx -> referenced by quote in scripts/seed_covenace_demo.py
  Collateral - Whole Eagle.xlsx                 -> not yet used
  Risk Grade Guidance_PD.xlsx                   -> not yet used (generic PD/LGD rubric, not borrower-specific)
```

## What the test cases actually demonstrate, and why they're not fabricated

Every expected value and every "actual output" below was read directly out
of the source files, not invented to make a test pass:

- **`net_sales_extraction_matches_source`** (passes): the Output Year
  memo's narrative states net sales of "$278.9 million" for 2024; the
  source PDF (page 3) states Net Sales of $278,884 (000s). Within a
  rounding tolerance, these agree.
- **`fy2024_dscr_incorrect_value`** (fails): the memo cites FY2024 DSCR of
  3.26x (from `Cash Flow Coverage Analysis`'s own calculation). The
  `Covenant Calculations` workbook -- the file actually named for covenant
  testing -- computes FY2024 DSCR as 2.64x for the same period, using a
  different debt-service definition. Treating the covenant workbook as the
  authoritative source, the memo's cited figure fails a numeric-tolerance
  check. This is a genuine discrepancy found while reading the files, not
  injected.
- **`fy2024_dscr_citation_mismatch`** (fails): same discrepancy, viewed as
  a citation problem -- the memo's DSCR claim cites `Cash Flow Coverage
  Analysis`, not the `Covenant Calculations` workbook that actually governs
  covenant testing.
- **`fy2024_dscr_conflict_not_flagged`** (fails): neither source document
  cross-references or flags the other's different DSCR figure for the same
  period. This test checks whether that conflict gets surfaced -- it
  genuinely isn't, in the real documents.
- **`contractual_covenant_threshold_missing`** (passes) and
  **`contractual_covenant_threshold_invented`** (fails, a clearly-labeled
  controlled negative case): none of the 8 source files contains an actual
  negotiated minimum-DSCR covenant threshold -- only historical ratios and
  a generic PD-scoring rubric. The "passes" case checks that's correctly
  reported as missing; the "fails" case is a deliberately constructed
  contrast (same pattern as the mock pack's `simulate_error` tests) proving
  the evaluator catches an invented value.
- **`credit_memo_hitl_gate`** (variant-dependent -- the regression case):
  the Output Year memo contains 8 literal, unresolved `HITL`/`HILT` review
  markers in its own text (management-change confirmation, three
  "please confirm the reason for the increase" flags, a 5-year-trend
  caveat, two risk/mitigant carry-forward flags, and one explicitly
  flagging that the PD/LGD grade itself needs human confirmation). The
  Prior Year memo has zero. Run against the `prior_year` output variant
  this passes; run against `output_year` it fails -- a real, found
  regression, not a scripted one.
