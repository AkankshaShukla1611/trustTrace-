from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.hitl_gate import HitlGateEvaluator

EVALUATOR = HitlGateEvaluator()
TEST_CASE = {"evaluator_config": {"hitl_gate": {"flags_field": "unresolved_hitl_flags", "required_clear": True}}, "severity": "critical"}


def test_passes_when_no_unresolved_flags_remain():
    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"unresolved_hitl_flags": []})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.PASS


def test_fails_when_unresolved_flags_remain():
    ctx = EvaluationContext(
        test_case=TEST_CASE,
        actual_output={"unresolved_hitl_flags": ["HITL - confirm X", "HITL - confirm Y"]},
    )
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.FAIL
    assert "2 unresolved" in outcome.reason


def test_unavailable_when_no_config_declared():
    ctx = EvaluationContext(test_case={"evaluator_config": {}}, actual_output={"unresolved_hitl_flags": []})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
