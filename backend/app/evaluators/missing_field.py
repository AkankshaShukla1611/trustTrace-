from __future__ import annotations

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


class MissingFieldEvaluator(BaseEvaluator):
    """
    Verifies that fields the test case declares should be absent from the
    source evidence are reported as missing (status == "missing", value
    is None), rather than the application inventing a value. Complements
    ConflictDetectionEvaluator, which covers the opposite labeled case
    (multiple disagreeing values).

    Config: evaluator_config["missing_field"] = {
      "fields_container": "fields", "expected_missing_fields": ["interest_rate"]
    }
    """

    name = "missing_field"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        config = ctx.evaluator_config(self.name)
        expected_missing_fields = config.get("expected_missing_fields", [])
        if not expected_missing_fields:
            return self.unavailable("test case declares no expected_missing_fields")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to check (execution did not produce output)")

        fields_container = config.get("fields_container", "fields")
        fields = ctx.actual_output.get(fields_container, {})

        invented = []
        details = {}
        for field_name in expected_missing_fields:
            field_result = fields.get(field_name, {})
            status = field_result.get("status")
            value = field_result.get("value")
            details[field_name] = {"status": status, "value": value}
            if not (status == "missing" and value is None):
                invented.append(field_name)

        if invented:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=(len(expected_missing_fields) - len(invented)) / len(expected_missing_fields),
                expected_value={f: "missing" for f in expected_missing_fields},
                actual_value=details,
                reason=f"invented a value for field(s) expected to be reported missing: {', '.join(invented)}",
                severity=ctx.test_case.get("severity"),
            )

        return EvaluationOutcome(
            status=EvaluatorStatus.PASS,
            score=1.0,
            expected_value={f: "missing" for f in expected_missing_fields},
            actual_value=details,
            reason="all expected-missing fields were correctly reported as missing, not invented",
        )
