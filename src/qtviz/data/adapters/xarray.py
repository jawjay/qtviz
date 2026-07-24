"""xarray adapter — labeled N-D arrays (D14/D17, milestone step 5).

Shape is the adapter's call (D17): a 1-D `DataArray` (or any `Dataset`) is
**tabular** — its dims/coords/variables are columns; an N-D `DataArray` is
**gridded**. `qv.tabular()` / `qv.gridded()` override. xarray objects may be
numpy- or dask-backed; a dask-backed object reports `is_lazy` and materializes
off the GUI thread.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ...core.disposable import NOOP
from ..accessor import resolve_expr
from ..ref import EagerGriddedRef, GriddedRef, Schema, TabularRef


def _is_lazy(obj) -> bool:
    chunks = getattr(obj, "chunks", None)
    return bool(chunks)  # None / empty mapping → eager; tuple / non-empty → dask-backed


class XarrayTabularRef(TabularRef):
    """A Dataset (or 1-D DataArray promoted to one): variables + coords are
    columns; resolve applies accessors to the Dataset (xarray broadcasts)."""

    def __init__(self, ds) -> None:
        self._ds = ds
        self.is_lazy = _is_lazy(ds)

    def schema(self) -> Schema:
        names = tuple(str(n) for n in (*self._ds.data_vars, *self._ds.coords))
        return Schema(names=names, kind="tabular")

    def size(self):
        sizes = self._ds.sizes
        return int(next(iter(sizes.values()))) if sizes else 0

    def extent(self, name):
        return None  # best-effort

    def fingerprint(self):
        return id(self._ds)

    def native(self) -> Any:
        return self._ds

    def subscribe(self, cb):
        return NOOP

    def resolve_channels(self, channels):
        out = {}
        for role, accessor in channels.items():
            expr = resolve_expr(accessor, columns=self._ds, native=self._ds)
            out[role] = np.asarray(getattr(expr, "values", expr))
        lengths = {len(a) for a in out.values()}
        if len(lengths) > 1:
            raise ValueError(
                f"channels resolved to mismatched lengths: { {r: len(a) for r, a in out.items()} }"
            )
        return out


class XarrayGriddedRef(GriddedRef):
    """An N-D DataArray: values grid + its first two dims' coordinates."""

    def __init__(self, da) -> None:
        self._da = da
        self.is_lazy = _is_lazy(da)

    def schema(self) -> Schema:
        return Schema(names=tuple(str(d) for d in self._da.dims),
                      kind="gridded", shape=tuple(self._da.shape))

    def size(self) -> int:
        return int(self._da.size)

    def fingerprint(self):
        return id(self._da)

    def native(self) -> Any:
        return self._da

    def extent(self, name):
        """Dim extents from the coord arrays ([D73]) — coords are small and
        eager even on a dask-backed DataArray, so this never computes values."""
        if name in self._da.coords:
            from ..ref import _numeric_extent  # noqa: PLC0415

            return _numeric_extent(np.asarray(self._da.coords[name].values))
        return None

    @staticmethod
    def _coord(da, dim, n) -> np.ndarray:
        if dim in da.coords:
            return np.asarray(da.coords[dim].values)
        return np.arange(n)

    def materialize(self, limit: int | None = None, *,
                    max_cells: int | None = None) -> EagerGriddedRef:
        from ..ref import decimation_strides  # noqa: PLC0415

        da = self._da
        strides = decimation_strides(da.shape, max_cells) if da.ndim >= 2 else None
        if strides is not None:
            da = da[:: strides[0], :: strides[1]]  # xarray slices coords with the data
        values = np.asarray(da.values)  # computes if dask-backed
        dims, shape = da.dims, da.shape
        y = self._coord(da, dims[0], shape[0])
        x = self._coord(da, dims[-1], shape[-1])
        return EagerGriddedRef(self._da, values, x, y)

    def grid(self, value: str | None = None):
        return self.materialize().grid(value)


class XarrayAdapter:
    priority = 7

    def handles(self, obj: Any) -> bool:
        return type(obj).__module__.startswith("xarray")

    def wrap(self, obj: Any, shape: str | None = None):
        import xarray as xr  # noqa: PLC0415

        if isinstance(obj, xr.Dataset):
            if shape == "gridded":
                data_vars = list(obj.data_vars)
                if len(data_vars) != 1:  # [D73]: only an unambiguous Dataset grids
                    raise TypeError(
                        f"gridded() on a Dataset needs exactly one data variable; "
                        f"got {data_vars} — pick one (e.g. ds[{data_vars[0]!r}])"
                    )
                return XarrayGriddedRef(obj[data_vars[0]])
            return XarrayTabularRef(obj)
        # DataArray
        if shape == "tabular" or (shape is None and obj.ndim == 1):
            return XarrayTabularRef(obj.to_dataset(name=obj.name or "values"))
        return XarrayGriddedRef(obj)
