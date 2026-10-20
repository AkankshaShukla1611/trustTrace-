from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.schema_correctness import SchemaCorrectnessEvaluator

EVALUATOR = SchemaCorrectnessEvaluator()


def _ctx(actual_output, config):
    return EvaluationContext(
        test_case={"evaluator_config": {"schema_correctness": config}},
        actual_output=actual_output,
    )


def test_passes_when_required_fields_types_and_enums_satisfied():
    config = {
        "required_fields": ["loan_amount", "status"],
        "field_types": {"loan_amount": "number"},
        "enums": {"status": ["approved", "pending"]},
    }
    outcome = EVALUATOR.evaluate(_ctx({"loan_amount": 100000, "status": "approved"}, config))
    assert outcome.status == EvaluatorStatus.PASS
    assert outcome.score == 1.0


def test_fails_on_missing_field_and_wrong_type_and_bad_enum():
    config = {
        "required_fields": ["loan_amount", "status"],
        "field_types": {"loan_amount": "number"},
        "enums": {"status": ["approved", "pending"]},
    }
    outcome = EVALUATOR.evaluate(_ctx({"loan_amount": "not-a-number", "status": "rejected"}, config))
    assert outcome.status == EvaluatorStatus.FAIL
    assert "wrong type" not in outcome.reason  # just sanity that reason text exists below
    assert "expected type number" in outcome.reason
    assert "not in allowed set" in outcome.reason


def test_unavailable_when_test_case_declares_no_schema():
    outcome = EVALUATOR.evaluate(EvaluationContext(test_case={"evaluator_config": {}}, actual_output={"a": 1}))
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
