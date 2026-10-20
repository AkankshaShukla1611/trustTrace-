from app.adapters.mock_adapter import MockAdapter

DOCUMENTS = [
    {
        "document_id": "loan_agreement",
        "pages": [
            {"page_number": 1, "text": "The total loan amount is 500000 dollars disbursed to the borrower."},
            {"page_number": 2, "text": "Unrelated boilerplate about governing law and jurisdiction."},
        ],
    }
]


def test_capabilities_are_declared_explicitly():
    adapter = MockAdapter(config={})
    caps = adapter.get_capabilities()
    assert caps.retrieved_passages is True
    assert caps.tool_calls is False  # mock adapter never fabricates tool calls


def test_validate_config_always_ok_for_mock():
    adapter = MockAdapter(config={})
    result = adapter.validate_config()
    assert result.ok is True


def test_qa_mode_answers_with_citation_when_relevant_passage_found():
    adapter = MockAdapter(config={})
    result = adapter.execute({"mode": "qa", "query": "total loan amount disbursed", "documents": DOCUMENTS})
    assert result.status == "ok"
    assert result.output["abstained"] is False
    assert result.output["citations"] == [{"document_id": "loan_agreement", "page": 1}]
    assert len(result.retrieved_passages) >= 1


def test_qa_mode_abstains_when_no_relevant_passage():
    adapter = MockAdapter(config={})
    result = adapter.execute({"mode": "qa", "query": "quantum entanglement physics", "documents": DOCUMENTS})
    assert result.status == "ok"
    assert result.output["abstained"] is True
    assert result.output["answer"] is None


def test_extract_mode_reports_missing_field_as_missing_not_invented():
    adapter = MockAdapter(config={})
    result = adapter.execute(
        {
            "mode": "extract",
            "documents": DOCUMENTS,
            "field_specs": [{"field_name": "interest_rate", "pattern": r"interest rate of ([\d.]+)%"}],
        }
    )
    assert result.status == "ok"
    assert result.output["fields"]["interest_rate"]["status"] == "missing"
    assert result.output["fields"]["interest_rate"]["value"] is None


def test_extract_mode_detects_conflicting_values_across_documents():
    conflicting_docs = DOCUMENTS + [
        {
            "document_id": "amendment",
            "pages": [{"page_number": 1, "text": "The total loan amount is 600000 dollars disbursed."}],
        }
    ]
    adapter = MockAdapter(config={})
    result = adapter.execute(
        {
            "mode": "extract",
            "documents": conflicting_docs,
            "field_specs": [{"field_name": "loan_amount", "pattern": r"total loan amount is (\d+)"}],
        }
    )
    assert result.output["fields"]["loan_amount"]["status"] == "conflict"


def test_force_abstain_config_represents_a_regressed_configuration():
    adapter = MockAdapter(config={"force_abstain": True})
    result = adapter.execute({"mode": "qa", "query": "total loan amount disbursed", "documents": DOCUMENTS})
    assert result.status == "ok"
    assert result.output["abstained"] is True
    assert result.config_metadata["force_abstain"] is True


def test_simulated_timeout_and_error_are_distinct_from_wrong_answer():
    adapter = MockAdapter(config={})
    timeout_result = adapter.execute({"mode": "simulate_timeout"})
    error_result = adapter.execute({"mode": "simulate_error"})
    assert timeout_result.status == "timeout"
    assert timeout_result.error_category == "timeout"
    assert error_result.status == "error"
    assert error_result.error_category == "adapter_error"
