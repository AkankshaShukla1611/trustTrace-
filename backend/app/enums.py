from enum import Enum


class IntegrationType(str, Enum):
    MOCK = "mock"
    HTTP = "http"
    PYTHON = "python"
    FILE = "file"


class IntegrationStatus(str, Enum):
    NOT_TESTED = "not_tested"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    FAILED = "failed"
    DISABLED = "disabled"


class ExecutionStatus(str, Enum):
    """Overall outcome of one test-case run. Distinct from individual evaluator status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    UNEVALUATED = "unevaluated"
    EXECUTION_ERROR = "execution_error"
    CANCELLED = "cancelled"


class EvaluatorStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INCONCLUSIVE = "inconclusive"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BehaviorType(str, Enum):
    """What kind of correctness check a test case expects."""

    EXACT_FIELDS = "exact_fields"
    FREE_TEXT = "free_text"
    ABSTAIN_EXPECTED = "abstain_expected"
    CONFLICT_FLAG_EXPECTED = "conflict_flag_expected"


class TraceStageStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class RunMode(str, Enum):
    SINGLE_CASE = "single_case"
    SELECTED_CASES = "selected_cases"
    FULL_DATASET = "full_dataset"
    AB_COMPARISON = "ab_comparison"
    REGRESSION = "regression"


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    ADAPTER_ERROR = "adapter_error"
    VALIDATION_ERROR = "validation_error"
    CONFIG_ERROR = "config_error"
    UNKNOWN = "unknown"
