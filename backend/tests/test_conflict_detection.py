from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.conflict_detection import ConflictDetectionEvaluator

EVALUATOR = ConflictDetectionEvaluator()
TEST_CASE = {
    "behavior_type": "conflict_flag_expected",
    "evaluator_config": {"conflict_detection": {"expected_conflict_fields": ["loan_amount"]}},
    "severity": "critical",
}


def test_passes_when_conflict_is_flagged():
    ctx = EvaluationContext(
        test_case=TEST_CASE,
        actual_output={"fields": {"loan_amount": {"status": "conflict", "conflicting_values": []}}},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS


def test_fails_when_conflicting_value_silently_picked():
    ctx = EvaluationContext(
        test_case=TEST_CASE,
        actual_output={"fields": {"loan_amount": {"status": "ok", "value": "500000"}}},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "loan_amount" in outcome.reason
