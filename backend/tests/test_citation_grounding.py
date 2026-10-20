from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.citation_grounding import CitationGroundingEvaluator

EVALUATOR = CitationGroundingEvaluator()

DOCUMENTS = {
    "doc1": {"pages": [{"page_number": 1, "text": "The borrower shall maintain a minimum current ratio of 1.5."}]},
}


def test_passes_when_citation_exists_relevant_and_supports_answer():
    ctx = EvaluationContext(
        test_case={
            "expected_evidence": [{"document_id": "doc1", "page": 1}],
        },
        actual_output={
            "answer": "The minimum current ratio is 1.5.",
            "citations": [{"document_id": "doc1", "page": 1}],
        },
        documents_by_id=DOCUMENTS,
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS


def test_fails_when_cited_page_does_not_exist():
    ctx = EvaluationContext(
        test_case={"expected_evidence": [{"document_id": "doc1", "page": 1}]},
        actual_output={"answer": "ratio is 1.5", "citations": [{"document_id": "doc1", "page": 99}]},
        documents_by_id=DOCUMENTS,
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "do not exist" in outcome.reason


def test_fails_when_citation_unrelated_to_answer_text():
    ctx = EvaluationContext(
        test_case={"expected_evidence": [{"document_id": "doc1", "page": 1}]},
        actual_output={"answer": "completely unrelated statement about weather", "citations": [{"document_id": "doc1", "page": 1}]},
        documents_by_id=DOCUMENTS,
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "overlap" in outcome.reason


def test_unavailable_when_no_citations_and_none_expected():
    ctx = EvaluationContext(
        test_case={"expected_evidence": []},
        actual_output={"answer": "no evidence needed here"},
        documents_by_id=DOCUMENTS,
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
