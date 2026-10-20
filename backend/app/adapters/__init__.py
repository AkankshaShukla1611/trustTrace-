from app.adapters.base import BaseAdapter, AdapterCapabilities, AdapterExecutionResult, ValidationResult
from app.adapters.registry import get_adapter_class, register_adapter

__all__ = [
    "BaseAdapter",
    "AdapterCapabilities",
    "AdapterExecutionResult",
    "ValidationResult",
    "get_adapter_class",
    "register_adapter",
]
