"""qtviz data layer — container-agnostic, lazy-first (spec §6)."""

from __future__ import annotations

from . import adapters as _adapters  # noqa: F401  — registers built-ins on import
from .ref import DataRef, EagerGriddedRef, EagerTabularRef, GridData, GriddedRef, Schema, TabularRef
from .registry import DataAdapter, as_data_ref, list_data_adapters, register_data_adapter

__all__ = [
    "DataRef",
    "TabularRef",
    "GriddedRef",
    "EagerTabularRef",
    "EagerGriddedRef",
    "Schema",
    "GridData",
    "DataAdapter",
    "as_data_ref",
    "register_data_adapter",
    "list_data_adapters",
]
