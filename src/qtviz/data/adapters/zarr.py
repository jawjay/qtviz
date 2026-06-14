"""zarr adapter — chunked, out-of-core N-D arrays (D17, milestone step 5).

A `zarr.Array` is gridded and lazy: shape/dtype are cheap metadata; the data
lives in (possibly on-disk/cloud) chunks until `materialize` slices it into
numpy, off the GUI thread.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..ref import EagerGriddedRef, GriddedRef, Schema


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

    def materialize(self, limit: int | None = None) -> EagerGriddedRef:
        return EagerGriddedRef(self._z, np.asarray(self._z[:]))

    def grid(self, value: str | None = None):
        return self.materialize().grid(value)


class ZarrAdapter:
    priority = 7

    def handles(self, obj: Any) -> bool:
        return type(obj).__module__.startswith("zarr")

    def wrap(self, obj: Any, shape: str | None = None):
        if shape == "tabular":
            raise TypeError("a zarr array is gridded; cannot force tabular")
        return ZarrGriddedRef(obj)
