from app.adapters.mock_adapter import MockAdapter
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


def test_against_genuinely_computed_output_not_a_hand_written_dict():
    """
    Unlike the tests above (which hand-write actual_output as a fixed
    "arrange" step -- standard unit-test practice, not evaluator
    hardcoding), this test produces actual_output by actually running the
    mock adapter's search/answer engine over the source document, then
    feeds that real result into the evaluator. Proves the evaluator's
    pass/fail isn't tied to anything hand-typed to match.
    """
    documents = [
        {
            "document_id": "doc1",
            "pages": [{"page_number": 1, "text": "The borrower shall maintain a minimum current ratio of 1.5."}],
        }
    ]
    adapter = MockAdapter(config={})
    adapter_result = adapter.execute({"mode": "qa", "query": "minimum current ratio requirement", "documents": documents})
    assert adapter_result.output["abstained"] is False  # sanity: the engine actually found something

    ctx = EvaluationContext(
        test_case={"expected_evidence": [{"document_id": "doc1", "page": 1}]},
        actual_output=adapter_result.output,
        documents_by_id={"doc1": documents[0]},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS
