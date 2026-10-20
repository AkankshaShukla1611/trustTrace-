from __future__ import annotations

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


class HitlGateEvaluator(BaseEvaluator):
    """
    Verifies that a document/output has no unresolved human-in-the-loop
    review flags before it is treated as finalized/approved -- an AI
    comment, risk factor, or assumption is not human-approved by default
    just because generation finished.

    Config: evaluator_config["hitl_gate"] = {
      "flags_field": "unresolved_hitl_flags", "required_clear": true
    }
    Expects actual_output[flags_field] to be a list; fails if non-empty
    while required_clear is true.
    """

    name = "hitl_gate"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        config = ctx.evaluator_config(self.name)
        if not config:
            return self.unavailable("test case declares no hitl_gate config")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to check (execution did not produce output)")

        flags_field = config.get("flags_field", "unresolved_hitl_flags")
        required_clear = config.get("required_clear", True)

        if flags_field not in ctx.actual_output:
            return self.unavailable(f"output has no '{flags_field}' field to check")

        flags = ctx.actual_output.get(flags_field) or []

        if required_clear and len(flags) > 0:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=0.0,
                expected_value={flags_field: []},
                actual_value={flags_field: flags},
                reason=f"{len(flags)} unresolved human-in-the-loop item(s) remain: {flags}",
                severity=ctx.test_case.get("severity"),
            )

        return EvaluationOutcome(
            status=EvaluatorStatus.PASS,
            score=1.0,
            expected_value={flags_field: []},
            actual_value={flags_field: flags},
            reason="no unresolved human-in-the-loop items remain",
        )
