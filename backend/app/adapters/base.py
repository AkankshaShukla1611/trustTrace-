from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AdapterCapabilities:
    """
    Explicit, per-adapter-instance capability declaration. The UI and the
    evaluation engine read this -- a capability left False must never be
    silently simulated or counted as passing.
    """

    validate_config: bool = False
    intermediate_traces: bool = False
    retrieved_passages: bool = False
    tool_calls: bool = False
    config_metadata: bool = False
    cleanup: bool = False

    def as_dict(self) -> dict:
        return {
            "validate_config": self.validate_config,
            "intermediate_traces": self.intermediate_traces,
            "retrieved_passages": self.retrieved_passages,
            "tool_calls": self.tool_calls,
            "config_metadata": self.config_metadata,
            "cleanup": self.cleanup,
        }


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""


@dataclass
class TraceEventData:
    stage_name: str
    status: str  # "ok" | "unavailable" | "error"
    payload: dict = field(default_factory=dict)


@dataclass
class AdapterExecutionResult:
    status: str  # "ok" | "error" | "timeout"
    output: dict | None = None
    error_category: str | None = None
    error_detail: str | None = None
    trace_events: list[TraceEventData] = field(default_factory=list)
    retrieved_passages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    config_metadata: dict = field(default_factory=dict)


class BaseAdapter(ABC):
    """
    The TrustTrace <-> target-application contract (Layer B).

    An adapter translates between a test case's `input_payload` and the
    target application's real invocation mechanism, then reports back
    exactly what it was able to observe. It must never fabricate a trace,
    retrieved passage, or tool call it did not actually get back from the
    target -- declare the capability False instead (see
    docs/adapter_guide.md for the full contract and a worked example).
    """

    adapter_type: str = "base"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def validate_config(self) -> ValidationResult:
        """Check the integration config is well-formed and the target is reachable."""
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> AdapterCapabilities:
        """Declare what this adapter instance can actually provide."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, input_payload: dict, *, timeout_seconds: float = 30.0) -> AdapterExecutionResult:
        """Run one test case's input against the target and return everything observed."""
        raise NotImplementedError

    def cleanup(self) -> None:
        """Override if the adapter holds a resource (connection, temp file) that needs closing."""
        return None
