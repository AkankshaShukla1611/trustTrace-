from __future__ import annotations
import re
from datetime import datetime

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome

_DEFAULT_RULE = {"type": "exact"}


def _normalize_string(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _compare_field(actual, expected, rule: dict) -> tuple[bool, str | None]:
    rule_type = rule.get("type", "exact")

    if expected is None:
        return actual is None, None

    if rule_type == "exact":
        return actual == expected, None

    if rule_type == "normalized_string":
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False, "normalized_string rule requires string values"
        return _normalize_string(actual) == _normalize_string(expected), None

    if rule_type == "numeric_tolerance":
        tolerance = rule.get("tolerance", 0)
        try:
            return abs(float(actual) - float(expected)) <= tolerance, None
        except (TypeError, ValueError):
            return False, "numeric_tolerance rule requires numeric values"

    if rule_type == "date":
        date_format = rule.get("format", "%Y-%m-%d")
        try:
            actual_date = datetime.strptime(str(actual), date_format)
            expected_date = datetime.strptime(str(expected), date_format)
            return actual_date == expected_date, None
        except ValueError:
            return False, f"could not parse dates with format '{date_format}'"

    return False, f"unknown comparison rule type '{rule_type}'"


class FactualCorrectnessEvaluator(BaseEvaluator):
    """
    Field-by-field comparison against test_case.expected_output. Applies
    only to behavior_type == "exact_fields" test cases -- a case expecting
    abstention or free-text behavior is out of scope for this evaluator
    (reported unavailable, not failed). Per-field comparison rules come
    from evaluator_config["factual_correctness"]["field_rules"]; fields
    with no rule default to an exact match, so distinct financial values
    are never silently treated as equivalent.
    """

    name = "factual_correctness"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        if ctx.test_case.get("behavior_type") != "exact_fields":
            return self.unavailable("test case behavior_type is not 'exact_fields'")

        expected_output = ctx.test_case.get("expected_output")
        if not expected_output:
            return self.unavailable("test case declares no expected_output")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to compare (execution did not produce output)")

        field_rules = ctx.evaluator_config(self.name).get("field_rules", {})

        mismatches = []
        rule_errors = []
        checked = 0
        correct = 0

        for field_name, expected_value in expected_output.items():
            checked += 1
            rule = field_rules.get(field_name, _DEFAULT_RULE)
            actual_value = ctx.actual_output.get(field_name)
            is_match, rule_error = _compare_field(actual_value, expected_value, rule)
            if rule_error:
                rule_errors.append(f"'{field_name}': {rule_error}")
                continue
            if is_match:
                correct += 1
            else:
                mismatches.append(f"'{field_name}' expected {expected_value!r}, got {actual_value!r}")

        score = correct / checked if checked else None

        if rule_errors:
            return EvaluationOutcome(
                status=EvaluatorStatus.ERROR,
                score=score,
                expected_value=expected_output,
                actual_value=ctx.actual_output,
                reason="; ".join(rule_errors),
            )

        if mismatches:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=score,
                expected_value=expected_output,
                actual_value=ctx.actual_output,
                reason="; ".join(mismatches),
                severity=ctx.test_case.get("severity"),
            )

        return EvaluationOutcome(
            status=EvaluatorStatus.PASS,
            score=score,
            expected_value=expected_output,
            actual_value=ctx.actual_output,
            reason=f"all {checked} field(s) matched",
        )
