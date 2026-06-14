"""qtviz data layer — container-agnostic, lazy-first (spec §6)."""

from __future__ import annotations

from . import adapters as _adapters  # noqa: F401  — registers built-ins on import
from .accessor import Accessor, accessor_columns, resolve_accessor
from .expr import Expr as Expression
from .expr import col, lit
from .pipeline import node_is_lazy, resolve_node
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
    # accessors (D14)
    "Accessor",
    "Expression",
    "col",
    "lit",
    "accessor_columns",
    "resolve_accessor",
    "resolve_node",
    "node_is_lazy",
]
