from __future__ import annotations
import importlib

from app.adapters.base import AdapterCapabilities, AdapterExecutionResult, BaseAdapter, TraceEventData, ValidationResult


class PythonAdapter(BaseAdapter):
    """
    Invokes an already-installed Python function as the target workflow.

    `module_path` must name a module already importable in TrustTrace's own
    environment (e.g. the target project installed as a package, or a
    thin wrapper module the target team provides). This is a
    deployment-time wiring decision made by whoever configures the
    integration -- it is NOT a mechanism for executing arbitrary code
    supplied through the API at request time, and integration config
    should only be editable by trusted operators.

    Config:
      {
        "module_path": "covenace_wrapper",
        "function_name": "run_extraction",
        "output_key": "output",
        "trace_key": "trace_events",            # optional: list of {stage_name, status, payload}
        "retrieved_passages_key": "passages",    # optional
        "tool_calls_key": "tool_calls",          # optional
        "config_metadata_key": "metadata"        # optional
      }

    The target function must accept the test case's input_payload (a dict)
    and return a dict. Any other shape is reported as a validation error,
    not silently coerced.
    """

    adapter_type = "python"

    def _resolve(self):
        module_path = self.config.get("module_path")
        function_name = self.config.get("function_name")
        if not module_path or not function_name:
            raise ValueError("module_path and function_name are required")
        module = importlib.import_module(module_path)
        func = getattr(module, function_name)
        return func

    def validate_config(self) -> ValidationResult:
        try:
            func = self._resolve()
        except (ValueError, ImportError, AttributeError) as exc:
            return ValidationResult(ok=False, message=str(exc))
        return ValidationResult(ok=True, message=f"resolved callable {func}")

    def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            validate_config=True,
            intermediate_traces=bool(self.config.get("trace_key")),
            retrieved_passages=bool(self.config.get("retrieved_passages_key")),
            tool_calls=bool(self.config.get("tool_calls_key")),
            config_metadata=bool(self.config.get("config_metadata_key")),
            cleanup=False,
        )

    def execute(self, input_payload: dict, *, timeout_seconds: float = 30.0) -> AdapterExecutionResult:
        try:
            func = self._resolve()
        except (ValueError, ImportError, AttributeError) as exc:
            return AdapterExecutionResult(status="error", error_category="config_error", error_detail=str(exc))

        try:
            result = func(input_payload)
        except Exception as exc:  # the target function is third-party code we don't control
            return AdapterExecutionResult(
                status="error", error_category="adapter_error", error_detail=f"{type(exc).__name__}: {exc}"
            )

        if not isinstance(result, dict):
            return AdapterExecutionResult(
                status="error", error_category="validation_error", error_detail="target function must return a dict"
            )

        output_key = self.config.get("output_key", "output")
        trace_key = self.config.get("trace_key")
        passages_key = self.config.get("retrieved_passages_key")
        tools_key = self.config.get("tool_calls_key")
        meta_key = self.config.get("config_metadata_key")

        trace_events = []
        if trace_key and isinstance(result.get(trace_key), list):
            for i, stage in enumerate(result[trace_key]):
                trace_events.append(
                    TraceEventData(
                        stage_name=stage.get("stage_name", f"stage_{i}"),
                        status=stage.get("status", "ok"),
                        payload=stage.get("payload", {}),
                    )
                )

        return AdapterExecutionResult(
            status="ok",
            output=result.get(output_key, result),
            trace_events=trace_events,
            retrieved_passages=result.get(passages_key, []) if passages_key else [],
            tool_calls=result.get(tools_key, []) if tools_key else [],
            config_metadata=result.get(meta_key, {}) if meta_key else {},
        )
