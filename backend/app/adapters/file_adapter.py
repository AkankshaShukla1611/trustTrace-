from __future__ import annotations

from app.adapters.base import AdapterCapabilities, AdapterExecutionResult, BaseAdapter, ValidationResult


class FileAdapter(BaseAdapter):
    """
    Evaluates a pre-exported output instead of invoking anything live.

    This mode cannot independently test the target application's internal
    execution -- it only evaluates whatever output and evidence were
    already exported into the test case's input_payload (under
    "supplied_output"). All capabilities beyond reading that payload are
    declared unavailable; this must never be presented as a live
    integration test.
    """

    adapter_type = "file"

    def validate_config(self) -> ValidationResult:
        return ValidationResult(ok=True, message="file/batch mode: no live connection to validate")

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            validate_config=True,
            intermediate_traces=False,
            retrieved_passages=True,
            tool_calls=False,
            config_metadata=False,
            cleanup=False,
        )

    def execute(self, input_payload: dict, *, timeout_seconds: float = 30.0) -> AdapterExecutionResult:
        supplied = input_payload.get("supplied_output")
        if supplied is None:
            return AdapterExecutionResult(
                status="error",
                error_category="validation_error",
                error_detail="file/batch test case is missing 'supplied_output'",
            )

        return AdapterExecutionResult(
            status="ok",
            output=supplied if isinstance(supplied, dict) else {"value": supplied},
            retrieved_passages=input_payload.get("supplied_evidence", []),
            config_metadata={"source": "file_batch_import", "live_execution": False},
        )
