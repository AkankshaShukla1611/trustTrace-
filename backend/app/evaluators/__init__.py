from app.enums import EvaluatorStatus, ExecutionStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome
from app.evaluators.schema_correctness import SchemaCorrectnessEvaluator
from app.evaluators.factual_correctness import FactualCorrectnessEvaluator
from app.evaluators.retrieval_metrics import RetrievalMetricsEvaluator
from app.evaluators.citation_grounding import CitationGroundingEvaluator
from app.evaluators.abstention import AbstentionEvaluator
from app.evaluators.conflict_detection import ConflictDetectionEvaluator
from app.evaluators.missing_field import MissingFieldEvaluator

DETERMINISTIC_EVALUATORS: list[BaseEvaluator] = [
    SchemaCorrectnessEvaluator(),
    FactualCorrectnessEvaluator(),
    RetrievalMetricsEvaluator(),
    CitationGroundingEvaluator(),
    AbstentionEvaluator(),
    ConflictDetectionEvaluator(),
    MissingFieldEvaluator(),
]


def compute_execution_status(outcomes: list[EvaluationOutcome]) -> ExecutionStatus:
    """
    Rolls up individual evaluator outcomes into one execution status.
    Unavailable results never count toward pass or fail; an execution
    with zero applicable evaluators is UNEVALUATED, not PASSED.
    """
    applicable = [o for o in outcomes if o.status != EvaluatorStatus.UNAVAILABLE]
    if not applicable:
        return ExecutionStatus.UNEVALUATED

    if any(o.status in (EvaluatorStatus.FAIL, EvaluatorStatus.ERROR) for o in applicable):
        return ExecutionStatus.FAILED

    return ExecutionStatus.PASSED


__all__ = [
    "BaseEvaluator",
    "EvaluationContext",
    "EvaluationOutcome",
    "DETERMINISTIC_EVALUATORS",
    "compute_execution_status",
]
