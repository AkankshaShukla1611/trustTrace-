from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.abstention import AbstentionEvaluator

EVALUATOR = AbstentionEvaluator()
TEST_CASE = {"behavior_type": "abstain_expected", "evaluator_config": {}, "severity": "high"}


def test_passes_when_application_correctly_abstains():
    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"abstained": True, "answer": None})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS


def test_fails_when_application_invents_an_answer():
    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"abstained": False, "answer": "$500,000"})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "invented" in outcome.reason


def test_fails_on_contradictory_abstain_with_value():
    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"abstained": True, "answer": "$500,000"})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "contradictory" in outcome.reason


def test_zero_value_is_not_confused_with_missing():
    # abstained True but value_field explicitly configured to a numeric field
    # that legitimately holds 0 -- this must not be flagged as "invented"
    # because 0 is a real zero value, distinct from "no value reported".
    ctx = EvaluationContext(
        test_case={**TEST_CASE, "evaluator_config": {"abstention": {"value_field": "numeric_answer"}}},
        actual_output={"abstained": True, "numeric_answer": None},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS
