"""
Tests the execution-status rollup's handling of INCONCLUSIVE results
(from the optional LLM judge): it must become NEEDS_REVIEW, never
silently default to PASSED, and a real FAIL still wins over it.
"""
from app.enums import EvaluatorStatus, ExecutionStatus
from app.evaluators import compute_execution_status
from app.evaluators.base import EvaluationOutcome


def test_all_unavailable_is_unevaluated():
    outcomes = [EvaluationOutcome(status=EvaluatorStatus.UNAVAILABLE)]
    assert compute_execution_status(outcomes) == ExecutionStatus.UNEVALUATED


def test_inconclusive_alone_is_needs_review_not_passed():
    outcomes = [
        EvaluationOutcome(status=EvaluatorStatus.UNAVAILABLE),
        EvaluationOutcome(status=EvaluatorStatus.INCONCLUSIVE),
    ]
    assert compute_execution_status(outcomes) == ExecutionStatus.NEEDS_REVIEW


def test_pass_plus_inconclusive_is_still_needs_review():
    # A deterministic pass doesn't excuse an inconclusive judge verdict --
    # the execution isn't confidently correct just because one check passed.
    outcomes = [
        EvaluationOutcome(status=EvaluatorStatus.PASS),
        EvaluationOutcome(status=EvaluatorStatus.INCONCLUSIVE),
    ]
    assert compute_execution_status(outcomes) == ExecutionStatus.NEEDS_REVIEW


def test_fail_beats_inconclusive():
    outcomes = [
        EvaluationOutcome(status=EvaluatorStatus.FAIL),
        EvaluationOutcome(status=EvaluatorStatus.INCONCLUSIVE),
    ]
    assert compute_execution_status(outcomes) == ExecutionStatus.FAILED


def test_all_pass_is_still_passed():
    outcomes = [EvaluationOutcome(status=EvaluatorStatus.PASS), EvaluationOutcome(status=EvaluatorStatus.PASS)]
    assert compute_execution_status(outcomes) == ExecutionStatus.PASSED
