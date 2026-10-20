from __future__ import annotations

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome

_TYPE_CHECKS = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class SchemaCorrectnessEvaluator(BaseEvaluator):
    """
    Required-field, type, and enum validation against a schema declared in
    the test case's evaluator_config["schema_correctness"]:
      {"required_fields": [...], "field_types": {field: "number"|...}, "enums": {field: [...]}}
    Unavailable when the test case declares no schema -- never silently
    skipped as a pass.
    """

    name = "schema_correctness"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        config = ctx.evaluator_config(self.name)
        if not config:
            return self.unavailable("test case declares no schema_correctness config")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to validate (execution did not produce output)")

        required_fields = config.get("required_fields", [])
        field_types = config.get("field_types", {})
        enums = config.get("enums", {})

        failures = []

        for field_name in required_fields:
            if field_name not in ctx.actual_output or ctx.actual_output[field_name] is None:
                failures.append(f"missing required field '{field_name}'")

        for field_name, type_name in field_types.items():
            if field_name not in ctx.actual_output or ctx.actual_output[field_name] is None:
                continue
            expected_type = _TYPE_CHECKS.get(type_name)
            value = ctx.actual_output[field_name]
            if expected_type and not isinstance(value, expected_type):
                failures.append(
                    f"field '{field_name}' expected type {type_name}, got {type(value).__name__}"
                )
            if type_name in ("number", "integer") and isinstance(value, bool):
                failures.append(f"field '{field_name}' expected {type_name}, got boolean")

        for field_name, allowed_values in enums.items():
            if field_name not in ctx.actual_output or ctx.actual_output[field_name] is None:
                continue
            value = ctx.actual_output[field_name]
            if value not in allowed_values:
                failures.append(f"field '{field_name}' value '{value}' not in allowed set {allowed_values}")

        if failures:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=0.0,
                expected_value=config,
                actual_value=ctx.actual_output,
                reason="; ".join(failures),
                severity=ctx.test_case.get("severity"),
            )

        return EvaluationOutcome(
            status=EvaluatorStatus.PASS,
            score=1.0,
            expected_value=config,
            actual_value=ctx.actual_output,
            reason="all required fields, types, and enums satisfied",
        )
