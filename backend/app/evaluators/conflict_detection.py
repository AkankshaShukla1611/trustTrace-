from __future__ import annotations

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


class ConflictDetectionEvaluator(BaseEvaluator):
    """
    For test cases where sources disagree, verifies the application
    flagged the conflict rather than silently picking one value. Does
    NOT assume any universal resolution policy (e.g. "newest document
    wins") -- it only checks that a conflict was surfaced, since the
    actual resolution rule is domain-configured, not a core assumption.

    Config: evaluator_config["conflict_detection"] = {
      "fields_container": "fields", "expected_conflict_fields": ["loan_amount"]
    }
    Expects actual_output[fields_container][field]["status"] == "conflict".
    """

    name = "conflict_detection"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        if ctx.test_case.get("behavior_type") != "conflict_flag_expected":
            return self.unavailable("test case behavior_type is not 'conflict_flag_expected'")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to check (execution did not produce output)")

        config = ctx.evaluator_config(self.name)
        fields_container = config.get("fields_container", "fields")
        expected_fields = config.get("expected_conflict_fields", [])
        if not expected_fields:
            return self.unavailable("test case declares no expected_conflict_fields")

        fields = ctx.actual_output.get(fields_container, {})
        missed = []
        details = {}
        for field_name in expected_fields:
            field_result = fields.get(field_name, {})
            status = field_result.get("status")
            details[field_name] = status
            if status != "conflict":
                missed.append(field_name)

        if missed:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=(len(expected_fields) - len(missed)) / len(expected_fields),
                expected_value={f: "conflict" for f in expected_fields},
                actual_value=details,
                reason=f"did not flag a conflict for: {', '.join(missed)}",
                severity=ctx.test_case.get("severity"),
            )

        return EvaluationOutcome(
            status=EvaluatorStatus.PASS,
            score=1.0,
            expected_value={f: "conflict" for f in expected_fields},
            actual_value=details,
            reason="all expected conflicts were flagged",
        )
