from app.adapters.file_adapter import FileAdapter


def test_single_supplied_output_is_evaluated_as_is():
    adapter = FileAdapter(config={})
    result = adapter.execute({"supplied_output": {"answer": "x"}, "supplied_evidence": [{"document_id": "d1", "page": 1}]})
    assert result.status == "ok"
    assert result.output == {"answer": "x"}
    assert result.retrieved_passages == [{"document_id": "d1", "page": 1}]
    assert result.config_metadata["live_execution"] is False


def test_missing_supplied_output_is_a_validation_error_not_a_crash():
    adapter = FileAdapter(config={})
    result = adapter.execute({})
    assert result.status == "error"
    assert result.error_category == "validation_error"


def test_output_variant_selects_the_matching_named_output():
    adapter_baseline = FileAdapter(config={"output_variant": "prior_year"})
    adapter_candidate = FileAdapter(config={"output_variant": "output_year"})
    input_payload = {
        "supplied_outputs": {
            "prior_year": {"unresolved_hitl_flags": []},
            "output_year": {"unresolved_hitl_flags": ["confirm X"]},
        }
    }
    baseline_result = adapter_baseline.execute(input_payload)
    candidate_result = adapter_candidate.execute(input_payload)
    assert baseline_result.output["unresolved_hitl_flags"] == []
    assert candidate_result.output["unresolved_hitl_flags"] == ["confirm X"]


def test_unknown_output_variant_is_a_config_error_not_a_silent_fallback():
    adapter = FileAdapter(config={"output_variant": "does_not_exist"})
    result = adapter.execute({"supplied_outputs": {"prior_year": {}}})
    assert result.status == "error"
    assert result.error_category == "config_error"


def test_capabilities_declare_no_live_execution():
    adapter = FileAdapter(config={})
    caps = adapter.get_capabilities()
    assert caps.intermediate_traces is False
    assert caps.tool_calls is False
