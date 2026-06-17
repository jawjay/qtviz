"""Pluggable data-adapter registry (spec §6.3).

`as_data_ref` walks registered adapters by descending priority. Optional
adapters auto-register iff their library imports — the data-side mirror of the
backend registry. Third parties can `register_data_adapter` their own.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..errors import AdapterError
from .ref import DataRef

# Any object a registered `DataAdapter` can wrap — a dict of columns, a numpy
# ndarray, a pandas/Arrow table, an xarray/zarr/dask object, or an already-built
# `DataRef`. Deliberately `Any` (the accepted set is open and extends with every
# registered adapter); it documents intent at every `data=` parameter without
# pinning the contract to optional dependencies.
DataLike = Any


@runtime_checkable
class DataAdapter(Protocol):
    priority: int

    def handles(self, obj: Any) -> bool: ...
    def wrap(self, obj: Any, shape: str | None = None) -> DataRef: ...


_ADAPTERS: list[DataAdapter] = []


def register_data_adapter(adapter: DataAdapter) -> None:
    _ADAPTERS.append(adapter)
    _ADAPTERS.sort(key=lambda a: -getattr(a, "priority", 0))


def list_data_adapters() -> list[DataAdapter]:
    return list(_ADAPTERS)


def as_data_ref(data: Any, *, shape: str | None = None) -> DataRef:
    """Wrap `data` in the matching `DataRef`. `shape` ("tabular" | "gridded")
    overrides the adapter's default shape choice (D17) — see `tabular`/`gridded`."""
    if isinstance(data, DataRef):
        return data
    for adapter in _ADAPTERS:
        if adapter.handles(data):
            return adapter.wrap(data, shape=shape)
    raise AdapterError(
        f"no data adapter handles {type(data).__name__!r}; "
        f"pass a dict / ndarray / DataFrame / Arrow / xarray / zarr / dask object, "
        f"or register an adapter"
    )


def tabular(data: Any) -> DataRef:
    """Force `data` to a tabular ref — e.g. a 1-D xarray DataArray as columns (D17)."""
    return as_data_ref(data, shape="tabular")


def gridded(data: Any) -> DataRef:
    """Force `data` to a gridded ref — e.g. a plain 2-D array as an image grid (D17)."""
    return as_data_ref(data, shape="gridded")
