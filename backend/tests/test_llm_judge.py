"""
Unit tests for the optional LLM judge evaluator. No real API key or
network call is needed: the Anthropic client is monkeypatched so these
tests verify TrustTrace's own logic (opt-in gating, response parsing,
verdict-to-status mapping, error handling) without depending on a real
model response -- but the request shape sent to the fake client is
checked against the real documented contract (output_config.format /
json_schema), the same way test_ocr_service.py checks Mistral's.
"""
import json

import pytest

from app.enums import EvaluatorStatus
from app.evaluators.base import EvaluationContext
from app.evaluators.llm_judge import LlmJudgeEvaluator

EVALUATOR = LlmJudgeEvaluator()

TEST_CASE = {
    "name": "Explains the covenant breach correctly",
    "description": "Free-text explanation, graded for correctness not exact wording",
    "input_payload": {"query": "Why did the DSCR covenant fail?"},
    "behavior_type": "free_text",
    "expected_output": {"summary": "DSCR fell below the 1.25x minimum required by the credit agreement"},
    "severity": "high",
    "evaluator_config": {"llm_judge": {}},
}


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, content):
        self.content = content


def _make_fake_client(response_json: dict, captured_calls: list):
    class FakeMessages:
        def create(self, **kwargs):
            captured_calls.append(kwargs)
            return _FakeResponse([_FakeTextBlock(json.dumps(response_json))])

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = FakeMessages()

    return FakeClient


def test_unavailable_when_no_config_declared(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    ctx = EvaluationContext(test_case={**TEST_CASE, "evaluator_config": {}}, actual_output={"x": 1})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE


def test_unavailable_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"x": 1})
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
    assert "ANTHROPIC_API_KEY" in outcome.reason


def test_passes_through_a_real_pass_verdict(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    calls = []
    fake_client_class = _make_fake_client(
        {"verdict": "pass", "reasoning": "Correctly cites the 1.25x DSCR minimum."}, calls
    )
    monkeypatch.setattr("anthropic.Anthropic", fake_client_class)

    ctx = EvaluationContext(
        test_case=TEST_CASE, actual_output={"summary": "DSCR dropped under the required 1.25x minimum"}
    )
    outcome = EVALUATOR.evaluate(ctx)

    assert outcome.status == EvaluatorStatus.PASS
    assert outcome.score == 1.0
    assert "1.25x" in outcome.reason
    assert outcome.limitations and "not a deterministic check" in outcome.limitations

    # verify the real documented request contract was used
    assert len(calls) == 1
    sent = calls[0]
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["output_config"]["format"]["schema"]["required"] == ["verdict", "reasoning"]
    assert sent["messages"][0]["role"] == "user"


def test_fail_verdict_carries_severity(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    calls = []
    fake_client_class = _make_fake_client(
        {"verdict": "fail", "reasoning": "Says the covenant was a leverage ratio, which is wrong."}, calls
    )
    monkeypatch.setattr("anthropic.Anthropic", fake_client_class)

    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"summary": "Leverage ratio exceeded 3.0x"})
    outcome = EVALUATOR.evaluate(ctx)

    assert outcome.status == EvaluatorStatus.FAIL
    assert outcome.score == 0.0
    assert outcome.severity == "high"


def test_inconclusive_verdict_is_never_a_pass(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    calls = []
    fake_client_class = _make_fake_client(
        {"verdict": "inconclusive", "reasoning": "Ambiguous whether this satisfies the criteria."}, calls
    )
    monkeypatch.setattr("anthropic.Anthropic", fake_client_class)

    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"summary": "something vague"})
    outcome = EVALUATOR.evaluate(ctx)

    assert outcome.status == EvaluatorStatus.INCONCLUSIVE
    assert outcome.score is None


def test_api_error_is_reported_as_error_not_silently_swallowed(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    class RaisingMessages:
        def create(self, **kwargs):
            raise RuntimeError("401 authentication_error")

    class RaisingClient:
        def __init__(self, *args, **kwargs):
            self.messages = RaisingMessages()

    monkeypatch.setattr("anthropic.Anthropic", RaisingClient)

    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"summary": "anything"})
    outcome = EVALUATOR.evaluate(ctx)

    assert outcome.status == EvaluatorStatus.ERROR
    assert "401" in outcome.reason


def test_unparseable_response_is_inconclusive_not_a_crash(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    calls = []

    class BadJsonMessages:
        def create(self, **kwargs):
            return _FakeResponse([_FakeTextBlock("not valid json at all")])

    class BadJsonClient:
        def __init__(self, *args, **kwargs):
            self.messages = BadJsonMessages()

    monkeypatch.setattr("anthropic.Anthropic", BadJsonClient)

    ctx = EvaluationContext(test_case=TEST_CASE, actual_output={"summary": "anything"})
    outcome = EVALUATOR.evaluate(ctx)

    assert outcome.status == EvaluatorStatus.INCONCLUSIVE
    assert "could not parse" in outcome.reason


def test_unavailable_when_no_actual_output(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    ctx = EvaluationContext(test_case=TEST_CASE, actual_output=None)
    outcome = EVALUATOR.evaluate(ctx)
    assert outcome.status == EvaluatorStatus.UNAVAILABLE
