from app.enums import EvaluatorStatus, ExecutionStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome
from app.evaluators.schema_correctness import SchemaCorrectnessEvaluator
from app.evaluators.factual_correctness import FactualCorrectnessEvaluator
from app.evaluators.retrieval_metrics import RetrievalMetricsEvaluator
from app.evaluators.citation_grounding import CitationGroundingEvaluator
from app.evaluators.abstention import AbstentionEvaluator
from app.evaluators.conflict_detection import ConflictDetectionEvaluator
from app.evaluators.missing_field import MissingFieldEvaluator
from app.evaluators.hitl_gate import HitlGateEvaluator
from app.evaluators.llm_judge import LlmJudgeEvaluator

DETERMINISTIC_EVALUATORS: list[BaseEvaluator] = [
    SchemaCorrectnessEvaluator(),
    FactualCorrectnessEvaluator(),
    RetrievalMetricsEvaluator(),
    CitationGroundingEvaluator(),
    AbstentionEvaluator(),
    ConflictDetectionEvaluator(),
    MissingFieldEvaluator(),
    HitlGateEvaluator(),
]

OPTIONAL_EVALUATORS: list[BaseEvaluator] = [
    LlmJudgeEvaluator(),
]
"""
Non-deterministic evaluators. Always attempted, but each one reports
`unavailable` unless both its test case opts in via evaluator_config and
any API key it needs is configured -- so the free local demo still needs
none of these to run.
"""

ALL_EVALUATORS: list[BaseEvaluator] = DETERMINISTIC_EVALUATORS + OPTIONAL_EVALUATORS


def compute_execution_status(outcomes: list[EvaluationOutcome]) -> ExecutionStatus:
    """
    Rolls up individual evaluator outcomes into one execution status.
    Unavailable results never count toward pass or fail; an execution
    with zero applicable evaluators is UNEVALUATED, not PASSED. A FAIL
    or ERROR always wins. Otherwise, any INCONCLUSIVE result (from the
    optional LLM judge) marks the execution NEEDS_REVIEW rather than
    letting it default to PASSED -- an inconclusive judgment is not
    evidence of correctness.
    """
    applicable = [o for o in outcomes if o.status != EvaluatorStatus.UNAVAILABLE]
    if not applicable:
        return ExecutionStatus.UNEVALUATED

    if any(o.status in (EvaluatorStatus.FAIL, EvaluatorStatus.ERROR) for o in applicable):
        return ExecutionStatus.FAILED

    if any(o.status == EvaluatorStatus.INCONCLUSIVE for o in applicable):
        return ExecutionStatus.NEEDS_REVIEW

    return ExecutionStatus.PASSED


__all__ = [
    "BaseEvaluator",
    "EvaluationContext",
    "EvaluationOutcome",
    "DETERMINISTIC_EVALUATORS",
    "OPTIONAL_EVALUATORS",
    "ALL_EVALUATORS",
    "compute_execution_status",
]
