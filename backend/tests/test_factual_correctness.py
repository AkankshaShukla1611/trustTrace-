from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.factual_correctness import FactualCorrectnessEvaluator

EVALUATOR = FactualCorrectnessEvaluator()


def _test_case(expected_output, field_rules=None):
    return {
        "behavior_type": "exact_fields",
        "expected_output": expected_output,
        "evaluator_config": {"factual_correctness": {"field_rules": field_rules or {}}},
        "severity": "high",
    }


def test_passes_on_exact_match():
    ctx = EvaluationContext(
        test_case=_test_case({"loan_id": "LN-001", "loan_amount": 500000}),
        actual_output={"loan_id": "LN-001", "loan_amount": 500000},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS
    assert outcome.score == 1.0


def test_fails_on_distinct_numeric_value_even_though_close():
    # Values are close (within 1%) but no tolerance is configured, so a
    # distinct financial value must NOT be treated as equivalent.
    ctx = EvaluationContext(
        test_case=_test_case({"loan_amount": 500000}),
        actual_output={"loan_amount": 500001},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "loan_amount" in outcome.reason


def test_numeric_tolerance_rule_allows_configured_slack():
    ctx = EvaluationContext(
        test_case=_test_case({"loan_amount": 500000.00}, field_rules={"loan_amount": {"type": "numeric_tolerance", "tolerance": 1.0}}),
        actual_output={"loan_amount": 500000.50},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS


def test_unavailable_when_behavior_type_is_not_exact_fields():
    ctx = EvaluationContext(
        test_case={"behavior_type": "abstain_expected", "expected_output": {"x": 1}, "evaluator_config": {}},
        actual_output={"x": 1},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
