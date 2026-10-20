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

    For A/B and regression runs in file/batch mode (where there's no live
    app to reconfigure), the integration config may set
    {"output_variant": "<name>"} and the test case's input_payload may
    provide "supplied_outputs": {"<name>": {...}, ...} /
    "supplied_evidences": {"<name>": [...]} instead of a single
    "supplied_output" -- the adapter then serves the named variant. Test
    cases with only "supplied_output" behave identically regardless of
    output_variant.
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
        variant = self.config.get("output_variant")

        if variant and "supplied_outputs" in input_payload:
            if variant not in input_payload["supplied_outputs"]:
                return AdapterExecutionResult(
                    status="error",
                    error_category="config_error",
                    error_detail=f"no supplied_outputs variant named '{variant}' on this test case",
                )
            supplied = input_payload["supplied_outputs"][variant]
            evidence = input_payload.get("supplied_evidences", {}).get(variant, [])
        else:
            supplied = input_payload.get("supplied_output")
            evidence = input_payload.get("supplied_evidence", [])

        if supplied is None:
            return AdapterExecutionResult(
                status="error",
                error_category="validation_error",
                error_detail="file/batch test case is missing 'supplied_output' (or a matching 'supplied_outputs' variant)",
            )

        return AdapterExecutionResult(
            status="ok",
            output=supplied if isinstance(supplied, dict) else {"value": supplied},
            retrieved_passages=evidence,
            config_metadata={"source": "file_batch_import", "live_execution": False, "output_variant": variant or "default"},
        )
