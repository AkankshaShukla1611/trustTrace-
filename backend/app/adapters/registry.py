from __future__ import annotations

from app.adapters.base import BaseAdapter
from app.enums import IntegrationType

_REGISTRY: dict[str, type[BaseAdapter]] = {}


def register_adapter(adapter_type: str, adapter_class: type[BaseAdapter]) -> None:
    _REGISTRY[adapter_type] = adapter_class


def get_adapter_class(adapter_type: str) -> type[BaseAdapter]:
    if adapter_type not in _REGISTRY:
        raise KeyError(f"no adapter registered for type '{adapter_type}'")
    return _REGISTRY[adapter_type]


def _register_builtin_adapters() -> None:
    from app.adapters.mock_adapter import MockAdapter
    from app.adapters.http_adapter import HttpAdapter
    from app.adapters.python_adapter import PythonAdapter
    from app.adapters.file_adapter import FileAdapter

    register_adapter(IntegrationType.MOCK.value, MockAdapter)
    register_adapter(IntegrationType.HTTP.value, HttpAdapter)
    register_adapter(IntegrationType.PYTHON.value, PythonAdapter)
    register_adapter(IntegrationType.FILE.value, FileAdapter)


_register_builtin_adapters()
