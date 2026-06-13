"""Pluggable data-adapter registry (spec §6.3).

`as_data_ref` walks registered adapters by descending priority. Optional
adapters auto-register iff their library imports — the data-side mirror of the
backend registry. Third parties can `register_data_adapter` their own.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..errors import AdapterError
from .ref import DataRef


@runtime_checkable
class DataAdapter(Protocol):
    priority: int

    def handles(self, obj: Any) -> bool: ...
    def wrap(self, obj: Any) -> DataRef: ...


_ADAPTERS: list[DataAdapter] = []


def register_data_adapter(adapter: DataAdapter) -> None:
    _ADAPTERS.append(adapter)
    _ADAPTERS.sort(key=lambda a: -getattr(a, "priority", 0))


def list_data_adapters() -> list[DataAdapter]:
    return list(_ADAPTERS)


def as_data_ref(data: Any) -> DataRef:
    if isinstance(data, DataRef):
        return data
    for adapter in _ADAPTERS:
        if adapter.handles(data):
            return adapter.wrap(data)
    raise AdapterError(
        f"no data adapter handles {type(data).__name__!r}; "
        f"pass a dict / ndarray / DataFrame / Arrow Table, or register an adapter"
    )
