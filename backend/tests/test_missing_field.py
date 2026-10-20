from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.missing_field import MissingFieldEvaluator

EVALUATOR = MissingFieldEvaluator()
TEST_CASE = {"evaluator_config": {"missing_field": {"expected_missing_fields": ["interest_rate"]}}, "severity": "medium"}


def test_passes_when_field_correctly_reported_missing():
    ctx = EvaluationContext(
        test_case=TEST_CASE,
        actual_output={"fields": {"interest_rate": {"status": "missing", "value": None}}},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS


def test_fails_when_value_invented_for_field_that_should_be_missing():
    ctx = EvaluationContext(
        test_case=TEST_CASE,
        actual_output={"fields": {"interest_rate": {"status": "ok", "value": "5.0"}}},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "interest_rate" in outcome.reason


def test_unavailable_when_no_expected_missing_fields_declared():
    ctx = EvaluationContext(test_case={"evaluator_config": {}}, actual_output={"fields": {}})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
