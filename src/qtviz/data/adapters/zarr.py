"""zarr adapter — chunked, out-of-core N-D arrays (D17, milestone step 5).

A `zarr.Array` is gridded and lazy: shape/dtype are cheap metadata; the data
lives in (possibly on-disk/cloud) chunks until `materialize` slices it into
numpy, off the GUI thread. A `zarr.Group` of 1-D arrays is **tabular** ([D73]):
its members are the columns (lengths validated), read lazily per column.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ...errors import AdapterError
from ..ref import (
    EagerGriddedRef,
    EagerTabularRef,
    GriddedRef,
    Schema,
    TabularRef,
    decimation_strides,
)


class ZarrGriddedRef(GriddedRef):
    is_lazy = True

    def __init__(self, z) -> None:
        self._z = z

    def schema(self) -> Schema:
        return Schema(names=(), kind="gridded", shape=tuple(self._z.shape))

    def size(self) -> int:
        return int(np.prod(self._z.shape))  # shape is cheap metadata

    def fingerprint(self):
        return id(self._z)

    def native(self) -> Any:
        return self._z

    def materialize(self, limit: int | None = None, *,
                    max_cells: int | None = None) -> EagerGriddedRef:
        strides = (decimation_strides(self._z.shape, max_cells)
                   if len(self._z.shape) >= 2 else None)
        if strides is None:
            return EagerGriddedRef(self._z, np.asarray(self._z[:]))
        sy, sx = strides
        values = np.asarray(self._z[::sy, ::sx])  # trailing (e.g. RGBA) dims untouched
        ny, nx = self._z.shape[0], self._z.shape[1]
        return EagerGriddedRef(self._z, values,
                               x=np.arange(0, nx, sx), y=np.arange(0, ny, sy))

    def grid(self, value: str | None = None):
        return self.materialize().grid(value)


class ZarrTabularRef(TabularRef):
    """A `zarr.Group` whose 1-D members are columns ([D73]). Lazy: schema comes
    from metadata; column data is read per-member at materialize."""

    is_lazy = True

    def __init__(self, group, names: tuple[str, ...], length: int) -> None:
        self._group = group
        self._names = names
        self._length = length

    def schema(self) -> Schema:
        return Schema(names=self._names, kind="tabular",
                      shape=(self._length, len(self._names)))

    def size(self) -> int:
        return self._length

    def fingerprint(self):
        return id(self._group)

    def native(self) -> Any:
        return self._group

    def series(self, name: str) -> np.ndarray:
        if name not in self._names:
            raise KeyError(f"no array {name!r} in group; available: {list(self._names)}")
        return np.asarray(self._group[name][:])

    def materialize(self, limit: int | None = None) -> EagerTabularRef:
        cols = {n: self.series(n) for n in self._names}
        return EagerTabularRef(self._group, cols)

    def resolve_channels(self, channels):
        return self.materialize().resolve_channels(channels)


def _wrap_group(group) -> ZarrTabularRef:
    names = tuple(sorted(group.array_keys()))
    if not names:
        raise AdapterError("zarr group has no member arrays to use as columns")
    lengths = set()
    for n in names:
        arr = group[n]
        if len(arr.shape) != 1:
            raise AdapterError(
                f"zarr group member {n!r} is {len(arr.shape)}-D; tabular columns "
                f"must be 1-D arrays (wrap an N-D member array directly for a grid)"
            )
        lengths.add(int(arr.shape[0]))
    if len(lengths) > 1:
        raise AdapterError(f"zarr group members have mismatched lengths: {sorted(lengths)}")
    return ZarrTabularRef(group, names, lengths.pop())


class ZarrAdapter:
    priority = 7

    def handles(self, obj: Any) -> bool:
        return type(obj).__module__.startswith("zarr")

    def wrap(self, obj: Any, shape: str | None = None):
        if hasattr(obj, "array_keys"):  # a Group → tabular ([D73])
            if shape == "gridded":
                raise TypeError("a zarr Group is tabular; wrap one member array for a grid")
            return _wrap_group(obj)
        if shape == "tabular":
            raise TypeError("a zarr array is gridded; cannot force tabular")
        return ZarrGriddedRef(obj)
