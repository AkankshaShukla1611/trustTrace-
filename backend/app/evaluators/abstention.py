from __future__ import annotations

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome


class AbstentionEvaluator(BaseEvaluator):
    """
    For test cases where the correct behavior is abstaining (missing
    required evidence), verifies the application reported that instead
    of inventing a value. Also catches the specific failure mode of
    reporting "abstained" while still returning a concrete value for the
    field in question -- an unknown value must never be conflated with a
    zero/negative one.

    Config: evaluator_config["abstention"] = {"abstain_field": "abstained", "value_field": "answer"}
    """

    name = "abstention"
    version = "1.0.0"

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        if ctx.test_case.get("behavior_type") != "abstain_expected":
            return self.unavailable("test case behavior_type is not 'abstain_expected'")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to check (execution did not produce output)")

        config = ctx.evaluator_config(self.name)
        abstain_field = config.get("abstain_field", "abstained")
        value_field = config.get("value_field", "answer")

        if abstain_field not in ctx.actual_output:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=0.0,
                expected_value={abstain_field: True},
                actual_value=ctx.actual_output,
                reason=f"output has no '{abstain_field}' field to confirm abstention",
                severity=ctx.test_case.get("severity"),
            )

        abstained = ctx.actual_output.get(abstain_field)

        if abstained is not True:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=0.0,
                expected_value={abstain_field: True},
                actual_value=ctx.actual_output,
                reason="application invented an answer where missing evidence required abstention",
                severity=ctx.test_case.get("severity"),
            )

        invented_value = ctx.actual_output.get(value_field)
        if invented_value is not None:
            return EvaluationOutcome(
                status=EvaluatorStatus.FAIL,
                score=0.0,
                expected_value={abstain_field: True, value_field: None},
                actual_value=ctx.actual_output,
                reason=(
                    f"reported abstained=True but also returned a non-null value for '{value_field}' "
                    f"({invented_value!r}) -- contradictory"
                ),
                severity=ctx.test_case.get("severity"),
            )

        return EvaluationOutcome(
            status=EvaluatorStatus.PASS,
            score=1.0,
            expected_value={abstain_field: True},
            actual_value=ctx.actual_output,
            reason="application correctly abstained instead of inventing a value",
        )
