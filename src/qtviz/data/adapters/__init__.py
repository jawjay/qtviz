"""Registers the eager built-in adapters on import.

Lazy/gridded adapters (xarray, zarr, dask) and the `qtviz.data_adapters`
entry-point land in Phase 4–5; each is purely additive.
"""

from __future__ import annotations

from ..registry import register_data_adapter
from .builtin import BUILTINS

for _adapter_cls in BUILTINS:
    register_data_adapter(_adapter_cls())
