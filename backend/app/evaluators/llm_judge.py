"""
Optional semantic judge for free-text correctness that lexical/exact
checks can't fairly grade (e.g. "does this explanation correctly convey
the right idea", not "does this string match exactly"). Deliberately
NOT in DETERMINISTIC_EVALUATORS -- see OPTIONAL_EVALUATORS in
app/evaluators/__init__.py.

Real Claude Messages API contract used here (verified against the
claude-api skill's bundled docs, not assumed): POST-equivalent
`client.messages.create(model=..., max_tokens=..., messages=[...],
output_config={"format": {"type": "json_schema", "schema": {...}}})`.
`output_config.format` guarantees the response's first content block is
text containing JSON that validates against the given schema, so no
"please respond in JSON" prompt-begging is needed. Uses Haiku (the
cheapest current model) by default since a judge call doesn't need
flagship capability.
"""
from __future__ import annotations
import json
import os

from app.enums import EvaluatorStatus
from app.evaluators.base import BaseEvaluator, EvaluationContext, EvaluationOutcome

DEFAULT_JUDGE_MODEL = "claude-haiku-5-5"

JUDGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "inconclusive"]},
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "reasoning"],
    "additionalProperties": False,
}

_VERDICT_TO_STATUS = {
    "pass": EvaluatorStatus.PASS,
    "fail": EvaluatorStatus.FAIL,
    "inconclusive": EvaluatorStatus.INCONCLUSIVE,
}

_LIMITATION_NOTE = (
    "LLM judge result -- a model's opinion, not a deterministic check. "
    "Never treat a judge verdict as unquestionable ground truth; review disputed results."
)


def build_judge_prompt(test_case: dict, actual_output: dict, criteria: str) -> str:
    return (
        "You are an impartial grader checking one AI system's output against a test case.\n\n"
        f"Test case name: {test_case.get('name')}\n"
        f"Description: {test_case.get('description') or '(none given)'}\n"
        f"Input given to the system: {json.dumps(test_case.get('input_payload'), default=str)}\n"
        f"Expected output / correct behavior: {json.dumps(test_case.get('expected_output'), default=str)}\n"
        f"(If no expected_output is given, the declared behavior_type is '{test_case.get('behavior_type')}'.)\n\n"
        f"Grading criteria: {criteria}\n\n"
        f"Actual output produced by the system:\n{json.dumps(actual_output, default=str)}\n\n"
        "Decide pass, fail, or inconclusive (if you genuinely cannot tell), and give a short reason."
    )


class LlmJudgeEvaluator(BaseEvaluator):
    """
    Judges free-text correctness using Claude as a semantic grader,
    strictly opt-in: unavailable unless the test case declares
    evaluator_config["llm_judge"] AND ANTHROPIC_API_KEY is configured --
    this evaluator is never required for the free local demo. Returns
    pass/fail/inconclusive; inconclusive never counts as a pass and
    flags the execution for human review. Every outcome carries a
    limitations note making clear this is a model's judgment, not a
    deterministic fact, per this project's stance that an LLM judge is
    not an unquestionable source of truth.
    """

    name = "llm_judge"
    version = "1.0.0"
    deterministic = False

    def evaluate(self, ctx: EvaluationContext) -> EvaluationOutcome:
        # An empty {} config is a valid opt-in (use defaults) -- unlike
        # evaluators that need specific sub-keys to do anything, this one
        # only needs to know the test case named it at all. Check key
        # presence, not truthiness, so {"llm_judge": {}} isn't mistaken
        # for "not opted in".
        if self.name not in (ctx.test_case.get("evaluator_config") or {}):
            return self.unavailable("test case declares no llm_judge config (this evaluator is opt-in)")
        config = ctx.evaluator_config(self.name)

        if not os.environ.get("ANTHROPIC_API_KEY"):
            return self.unavailable("ANTHROPIC_API_KEY is not configured -- the optional LLM judge is disabled")

        if ctx.actual_output is None:
            return self.unavailable("no actual output to judge (execution did not produce output)")

        criteria = config.get(
            "criteria",
            "Judge whether the actual output correctly and faithfully satisfies the expected "
            "output/behavior for this test case.",
        )
        model = config.get("model", DEFAULT_JUDGE_MODEL)

        try:
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{"role": "user", "content": build_judge_prompt(ctx.test_case, ctx.actual_output, criteria)}],
                output_config={"format": {"type": "json_schema", "schema": JUDGE_RESPONSE_SCHEMA}},
            )
        except Exception as exc:
            return EvaluationOutcome(
                status=EvaluatorStatus.ERROR,
                reason=f"LLM judge call failed: {type(exc).__name__}: {exc}",
                limitations=_LIMITATION_NOTE,
            )

        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            return EvaluationOutcome(
                status=EvaluatorStatus.INCONCLUSIVE,
                reason="judge response contained no text content",
                limitations=_LIMITATION_NOTE,
            )

        try:
            parsed = json.loads(text)
            verdict = parsed["verdict"]
            reasoning = parsed["reasoning"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return EvaluationOutcome(
                status=EvaluatorStatus.INCONCLUSIVE,
                reason=f"could not parse judge response: {exc}",
                limitations=_LIMITATION_NOTE,
            )

        status = _VERDICT_TO_STATUS.get(verdict, EvaluatorStatus.INCONCLUSIVE)
        return EvaluationOutcome(
            status=status,
            score={"pass": 1.0, "fail": 0.0}.get(verdict),
            expected_value=ctx.test_case.get("expected_output") or {"behavior_type": ctx.test_case.get("behavior_type")},
            actual_value=ctx.actual_output,
            reason=reasoning,
            evidence={"model": model, "criteria": criteria},
            limitations=_LIMITATION_NOTE,
            severity=ctx.test_case.get("severity") if status == EvaluatorStatus.FAIL else None,
        )
