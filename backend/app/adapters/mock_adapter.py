from __future__ import annotations
import time

from app.adapters.base import (
    AdapterCapabilities,
    AdapterExecutionResult,
    BaseAdapter,
    TraceEventData,
    ValidationResult,
)
from app.example_app import engine


class MockAdapter(BaseAdapter):
    """
    Wraps the deterministic example_app (Layer D) behind the standard
    adapter contract (Layer B). It proves the generic runner and
    evaluators work end to end without any external API or network call.

    Supported input_payload shapes:
      {"mode": "qa", "query": str, "documents": [...]}
      {"mode": "extract", "documents": [...], "field_specs": [{"field_name","pattern"}]}
      {"mode": "simulate_timeout"}      -- controlled failure for reliability tests
      {"mode": "simulate_error"}        -- controlled failure for reliability tests

    Integration config may set {"force_abstain": true} to represent a
    different/regressed configuration of the same target application
    (e.g. a broken retrieval step) for A/B and regression-run demos --
    it is a real, labeled behavior change in this adapter, not a
    post-hoc edit of results.
    """

    adapter_type = "mock"

    def validate_config(self) -> ValidationResult:
        return ValidationResult(ok=True, message="mock adapter requires no external configuration")

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            validate_config=True,
            intermediate_traces=True,
            retrieved_passages=True,
            tool_calls=False,
            config_metadata=True,
            cleanup=False,
        )

    def execute(self, input_payload: dict, *, timeout_seconds: float = 30.0) -> AdapterExecutionResult:
        mode = input_payload.get("mode", "qa")
        config_metadata = {"engine": "example_app.financial_qa", "version": "1.0.0", "deterministic": True}

        if mode == "simulate_timeout":
            return AdapterExecutionResult(
                status="timeout",
                error_category="timeout",
                error_detail="simulated timeout for reliability testing",
                config_metadata=config_metadata,
            )
        if mode == "simulate_error":
            return AdapterExecutionResult(
                status="error",
                error_category="adapter_error",
                error_detail="simulated adapter error for reliability testing",
                config_metadata=config_metadata,
            )

        documents = input_payload.get("documents", [])

        if mode == "extract":
            field_specs = input_payload.get("field_specs", [])
            trace = [
                TraceEventData(
                    stage_name="extract",
                    status="ok",
                    payload={"field_specs": field_specs, "document_count": len(documents)},
                )
            ]
            results = engine.extract_fields(documents, field_specs)
            return AdapterExecutionResult(
                status="ok",
                output={"fields": results},
                trace_events=trace,
                config_metadata=config_metadata,
            )

        # default: qa mode
        query = input_payload.get("query", "")
        if self.config.get("force_abstain"):
            config_metadata["force_abstain"] = True
            trace = [
                TraceEventData(stage_name="search", status="ok", payload={"query": query, "results": []}),
                TraceEventData(
                    stage_name="answer",
                    status="ok",
                    payload={"abstained": True, "reason": "force_abstain config enabled"},
                ),
            ]
            return AdapterExecutionResult(
                status="ok",
                output={"answer": None, "citations": [], "abstained": True, "reason": "force_abstain config enabled"},
                trace_events=trace,
                retrieved_passages=[],
                config_metadata=config_metadata,
            )

        search_results = engine.search_passages(documents, query)
        answer_result = engine.answer_question(documents, query)
        trace = [
            TraceEventData(stage_name="search", status="ok", payload={"query": query, "results": search_results}),
            TraceEventData(
                stage_name="answer",
                status="ok",
                payload={"abstained": answer_result["abstained"], "reason": answer_result["reason"]},
            ),
        ]
        return AdapterExecutionResult(
            status="ok",
            output={
                "answer": answer_result["answer"],
                "citations": answer_result["citations"],
                "abstained": answer_result["abstained"],
                "reason": answer_result["reason"],
            },
            trace_events=trace,
            retrieved_passages=search_results,
            config_metadata=config_metadata,
        )
