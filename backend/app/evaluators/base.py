from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.enums import EvaluatorStatus


@dataclass
class EvaluationContext:
    """
    Everything an evaluator might need. `test_case` is a plain dict (not an
    ORM row) so evaluators stay pure functions, independently unit
    testable with no database. Fields the adapter couldn't provide are
    empty/None -- evaluators must treat that as "unavailable", never as
    a passing or failing result.
    """

    test_case: dict[str, Any]
    actual_output: dict | None
    retrieved_passages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    config_metadata: dict = field(default_factory=dict)
    documents_by_id: dict[str, dict] = field(default_factory=dict)
    """document_id -> {"pages": [{"page_number", "text"}], ...} for grounding checks."""

    def evaluator_config(self, evaluator_name: str) -> dict:
        return self.test_case.get("evaluator_config", {}).get(evaluator_name, {})


@dataclass
class EvaluationOutcome:
    status: EvaluatorStatus
    score: float | None = None
    expected_value: Any = None
    actual_value: Any = None
    reason: str | None = None
    evidence: dict = field(default_factory=dict)
    limitations: str | None = None
    severity: str | None = None


class BaseEvaluator(ABC):
    name: str = "base_evaluator"
    version: str = "1.0.0"

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        raise NotImplementedError

    def unavailable(self, reason: str) -> EvaluationOutcome:
        return EvaluationOutcome(status=EvaluatorStatus.UNAVAILABLE, reason=reason)
