"""See CitationGroundingEvaluator's docstring for the three checks it runs."""
from __future__ import annotations
import re

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome

SUPPORT_OVERLAP_THRESHOLD = 0.15


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _find_page_text(ctx: EvaluationContext, document_id: str, page: int) -> str | None:
    doc = ctx.documents_by_id.get(document_id)
    if not doc:
        return None
    for p in doc.get("pages", []):
        if p.get("page_number") == page:
            return p.get("text", "")
    return None


class CitationGroundingEvaluator(BaseEvaluator):
    """
    Citation/evidence grounding: three independent checks, deliberately
    kept separate because a valid citation is not the same thing as a
    grounded answer.
      1. existence  -- does the cited document/page actually exist?
      2. relevance  -- does the citation point to a passage labeled
                        relevant for this test case?
      3. support    -- does the cited passage's text actually contain
                        enough overlap with the answer to plausibly
                        support it?

    Check 3 is a deterministic lexical-overlap heuristic, not true
    semantic entailment -- its limitation is reported in every outcome
    so it is never mistaken for a stronger guarantee.
    """

    name = "citation_grounding"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        if not ctx.actual_output:
            return self.unavailable("no actual output to check citations against")

        citations = ctx.actual_output.get("citations", [])
        expected_evidence = ctx.test_case.get("expected_evidence", [])

        if not citations:
            if expected_evidence:
                return EvaluationOutcome(
                    status=EvaluatorStatus.FAIL,
                    score=0.0,
                    expected_value=expected_evidence,
                    actual_value=[],
                    reason="no citations were provided but evidence was expected",
                    severity=ctx.test_case.get("severity"),
                )
            return self.unavailable("no citations to evaluate and none were expected")

        if not ctx.documents_by_id:
            return self.unavailable("source documents unavailable; cannot verify citation existence")

        expected_pairs = {(e.get("document_id"), e.get("page")) for e in expected_evidence}
        answer_text = ctx.actual_output.get("answer") or ""
        answer_tokens = _tokenize(answer_text) if answer_text else set()

        per_citation = []
        all_exist = True
        all_relevant = True
        all_supported = True

        for citation in citations:
            doc_id = citation.get("document_id")
            page = citation.get("page")
            page_text = _find_page_text(ctx, doc_id, page)
            exists = page_text is not None
            relevant = (doc_id, page) in expected_pairs if expected_pairs else None
            supported = None

            if exists and answer_tokens:
                page_tokens = _tokenize(page_text)
                overlap = len(answer_tokens & page_tokens) / len(answer_tokens)
                supported = overlap >= SUPPORT_OVERLAP_THRESHOLD

            all_exist = all_exist and exists
            if relevant is False:
                all_relevant = False
            if supported is False:
                all_supported = False

            per_citation.append(
                {"document_id": doc_id, "page": page, "exists": exists, "relevant": relevant, "supported": supported}
            )

        failures = []
        if not all_exist:
            failures.append("one or more cited document/page references do not exist")
        if expected_pairs and not all_relevant:
            failures.append("one or more citations do not point to a labeled relevant passage")
        if answer_tokens and not all_supported:
            failures.append("one or more citations do not lexically overlap with the answer text")

        status = EvaluatorStatus.FAIL if failures else EvaluatorStatus.PASS
        return EvaluationOutcome(
            status=status,
            score=1.0 if status == EvaluatorStatus.PASS else 0.0,
            expected_value=expected_evidence,
            actual_value=per_citation,
            reason="; ".join(failures) if failures else "all citations exist, are relevant, and overlap the answer",
            limitations="support check is lexical-overlap only, not semantic entailment",
            severity=ctx.test_case.get("severity") if status == EvaluatorStatus.FAIL else None,
        )
