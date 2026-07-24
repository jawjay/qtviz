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
    """zarr has no lazy views, so a `window()` ([D75]) is carried as index
    slices applied at read time — one `z[y0:y1:sy, x0:x1:sx]` touches only the
    chunks the (strided) window intersects."""

    is_lazy = True

    def __init__(self, z, win: tuple[slice, slice] | None = None) -> None:
        self._z = z
        self._win = win  # (y-slice, x-slice) in source index space

    def _yx(self) -> tuple[slice, slice]:
        if self._win is not None:
            return self._win
        return slice(0, int(self._z.shape[0])), slice(0, int(self._z.shape[1]))

    def schema(self) -> Schema:
        wy, wx = self._yx()
        shape = (wy.stop - wy.start, wx.stop - wx.start, *self._z.shape[2:])
        return Schema(names=(), kind="gridded", shape=shape)

    def size(self) -> int:
        return int(np.prod(self.schema().shape))

    def fingerprint(self):
        return (id(self._z), self._win and (self._win[0].start, self._win[0].stop,
                                            self._win[1].start, self._win[1].stop))

    def native(self) -> Any:
        return self._z

    def window(self, x: tuple | None = None, y: tuple | None = None) -> ZarrGriddedRef:
        """A narrowed lazy ref over **index-space** ranges (gridded contract,
        [D75]); nothing is read until materialize."""
        wy, wx = self._yx()

        def clip(rng, cur: slice, n: int) -> slice:
            if rng is None:
                return cur
            lo = max(cur.start, cur.start + int(np.floor(rng[0])))
            hi = min(cur.stop, cur.start + int(np.ceil(rng[1])))
            return slice(min(lo, n - 1), max(hi, lo + 1))

        return ZarrGriddedRef(self._z, (clip(y, wy, self._z.shape[0]),
                                        clip(x, wx, self._z.shape[1])))

    def materialize(self, limit: int | None = None, *,
                    max_cells: int | None = None) -> EagerGriddedRef:
        wy, wx = self._yx()
        shape = (wy.stop - wy.start, wx.stop - wx.start)
        strides = decimation_strides(shape, max_cells) if len(self._z.shape) >= 2 else None
        sy, sx = strides or (1, 1)
        values = np.asarray(self._z[wy.start:wy.stop:sy, wx.start:wx.stop:sx])
        return EagerGriddedRef(self._z, values,
                               x=np.arange(wx.start, wx.stop, sx),
                               y=np.arange(wy.start, wy.stop, sy))

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
