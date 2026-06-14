"""Registers the data adapters on import.

The eager built-ins (dict/numpy/pandas/arrow) and the dask adapter detect their
container by type/`sys.modules`, so they register unconditionally and stay inert
until such an object is actually wrapped. Other lazy/gridded adapters (xarray,
zarr) and the `qtviz.data_adapters` entry-point land in step 5; each is purely
additive.
"""

from __future__ import annotations

from ..registry import register_data_adapter
from .builtin import BUILTINS
from .dask import DaskAdapter
from .xarray import XarrayAdapter
from .zarr import ZarrAdapter

for _adapter_cls in (*BUILTINS, DaskAdapter, XarrayAdapter, ZarrAdapter):
    register_data_adapter(_adapter_cls())
