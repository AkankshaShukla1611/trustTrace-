from __future__ import annotations
import os

import httpx

from app.adapters.base import AdapterCapabilities, AdapterExecutionResult, BaseAdapter, ValidationResult


def _get_by_path(data, path: str):
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class HttpAdapter(BaseAdapter):
    """
    Configurable adapter for target applications that expose an HTTP API.

    Expected config shape (JSON-safe, persisted on the Integration row):
      {
        "base_url": "http://localhost:8080",
        "endpoint": "/qa",
        "method": "POST",
        "timeout_seconds": 30,
        "headers": {"X-Client": "trusttrace"},
        "auth": {"type": "bearer"|"api_key"|"none", "secret_env_var": "TARGET_API_KEY", "header_name": "X-API-Key"},
        "request_mapping": {"question": "query", "docs": "documents"},
        "response_mapping": {
          "output_path": "data.result",
          "retrieved_passages_path": "data.passages",
          "tool_calls_path": "data.tool_calls",
          "config_metadata_path": "data.meta"
        }
      }

    Secrets are never stored in `config` -- `auth.secret_env_var` names an
    environment variable resolved at call time (see .env.example). If that
    variable isn't set, the adapter sends the request without credentials
    rather than failing silently with a fabricated success.
    """

    adapter_type = "http"

    def validate_config(self) -> ValidationResult:
        base_url = self.config.get("base_url")
        endpoint = self.config.get("endpoint")
        if not base_url or not endpoint:
            return ValidationResult(ok=False, message="base_url and endpoint are required")
        try:
            resp = httpx.request("GET", base_url, timeout=self.config.get("timeout_seconds", 10.0))
            return ValidationResult(ok=True, message=f"reached {base_url} (status {resp.status_code})")
        except httpx.HTTPError as exc:
            return ValidationResult(ok=False, message=f"could not reach {base_url}: {type(exc).__name__}")

    def get_capabilities(self) -> AdapterCapabilities:
        mapping = self.config.get("response_mapping", {})
        return AdapterCapabilities(
            validate_config=True,
            intermediate_traces=False,
            retrieved_passages=bool(mapping.get("retrieved_passages_path")),
            tool_calls=bool(mapping.get("tool_calls_path")),
            config_metadata=bool(mapping.get("config_metadata_path")),
            cleanup=False,
        )

    def _headers(self) -> dict:
        headers = dict(self.config.get("headers", {}))
        auth = self.config.get("auth", {})
        secret_value = os.environ.get(auth.get("secret_env_var", ""), "")
        if auth.get("type") == "bearer" and secret_value:
            headers["Authorization"] = f"Bearer {secret_value}"
        elif auth.get("type") == "api_key" and secret_value:
            headers[auth.get("header_name", "X-API-Key")] = secret_value
        return headers

    def execute(self, input_payload: dict, *, timeout_seconds: float = 30.0) -> AdapterExecutionResult:
        base_url = self.config["base_url"]
        endpoint = self.config["endpoint"]
        method = self.config.get("method", "POST")

        request_mapping = self.config.get("request_mapping")
        if request_mapping:
            body = {target: _get_by_path(input_payload, source) for target, source in request_mapping.items()}
        else:
            body = input_payload

        url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
        try:
            resp = httpx.request(
                method,
                url,
                json=body,
                headers=self._headers(),
                timeout=self.config.get("timeout_seconds", timeout_seconds),
            )
        except httpx.TimeoutException:
            return AdapterExecutionResult(
                status="timeout", error_category="timeout", error_detail="request timed out"
            )
        except httpx.HTTPError as exc:
            return AdapterExecutionResult(
                status="error", error_category="adapter_error", error_detail=type(exc).__name__
            )

        if resp.status_code >= 400:
            return AdapterExecutionResult(
                status="error", error_category="adapter_error", error_detail=f"HTTP {resp.status_code}"
            )

        try:
            data = resp.json()
        except ValueError:
            return AdapterExecutionResult(
                status="error", error_category="validation_error", error_detail="response was not valid JSON"
            )

        mapping = self.config.get("response_mapping", {})
        output = _get_by_path(data, mapping["output_path"]) if mapping.get("output_path") else data
        retrieved_passages = (_get_by_path(data, mapping["retrieved_passages_path"]) or []) if mapping.get(
            "retrieved_passages_path"
        ) else []
        tool_calls = (_get_by_path(data, mapping["tool_calls_path"]) or []) if mapping.get("tool_calls_path") else []
        config_metadata = (_get_by_path(data, mapping["config_metadata_path"]) or {}) if mapping.get(
            "config_metadata_path"
        ) else {}

        return AdapterExecutionResult(
            status="ok",
            output=output if isinstance(output, dict) else {"value": output},
            retrieved_passages=retrieved_passages if isinstance(retrieved_passages, list) else [],
            tool_calls=tool_calls if isinstance(tool_calls, list) else [],
            config_metadata=config_metadata if isinstance(config_metadata, dict) else {},
        )
