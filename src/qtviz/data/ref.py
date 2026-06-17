"""The container-agnostic data handle (spec §2.1, §6).

Two shapes under one contract: `TabularRef` (named columns) and `GriddedRef`
(named dims). Cheap metadata is sync; the single expensive op (`materialize`)
is where lazy refs become eager. Phase 1 ships the eager refs below; lazy
adapters (dask/zarr) implement the same base.
"""

from __future__ import annotations

from collections import namedtuple
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..core.disposable import NOOP, Disposable
from ..errors import ValidationError

GridData = namedtuple("GridData", "values x y")


@dataclass(frozen=True)
class Schema:
    names: tuple[str, ...]
    kind: str  # "tabular" | "gridded"
    dtypes: tuple[str, ...] = ()
    shape: tuple[int, ...] | None = None


class DataRef:
    """Base handle. Subclass via TabularRef / GriddedRef."""

    is_lazy: bool = False

    def resolve_channels(self, channels: dict[str, Any]) -> dict[str, np.ndarray]:
        """Resolve `{role: accessor}` to `{role: 1-D ndarray}`, computing all
        channels together (lazy refs push projection down). Default: empty."""
        return {}

    def schema(self) -> Schema:
        raise NotImplementedError

    def size(self) -> int | None:
        raise NotImplementedError

    def extent(self, name: str) -> tuple[float, float] | None:
        return None

    def select(self, names: Sequence[str]) -> DataRef:
        return self

    def window(self, **ranges: Any) -> DataRef:
        return self

    def fingerprint(self):
        raise NotImplementedError

    def subscribe(self, cb: Callable[[Any], None]) -> Disposable:
        return NOOP

    def native(self) -> Any:
        raise NotImplementedError

    def materialize(self) -> DataRef:
        return self


class TabularRef(DataRef):
    def series(self, name: str) -> np.ndarray:
        raise NotImplementedError


class GriddedRef(DataRef):
    def grid(self, value: str | None = None) -> GridData:
        raise NotImplementedError


def _numeric_extent(arr: np.ndarray) -> tuple[float, float] | None:
    try:
        a = np.asarray(arr, dtype="float64")
    except (ValueError, TypeError):
        return None
    if a.size == 0:
        return None
    lo, hi = float(np.nanmin(a)), float(np.nanmax(a))
    if np.isnan(lo) or np.isnan(hi):
        return None
    return (lo, hi)


class EagerTabularRef(TabularRef):
    """In-memory tabular ref over a dict of 1-D numpy columns. `fingerprint`
    keys off the *source* object so equality means 'same data object'."""

    is_lazy = False

    def __init__(self, source: Any, columns: dict[str, np.ndarray]) -> None:
        self._source = source
        self._cols = columns

    def resolve_channels(self, channels: dict[str, Any]) -> dict[str, np.ndarray]:
        from .accessor import resolve_accessor  # noqa: PLC0415

        out = {
            role: resolve_accessor(accessor, columns=self._cols, native=self._source)
            for role, accessor in channels.items()
        }
        lengths = {len(a) for a in out.values()}
        if len(lengths) > 1:
            raise ValidationError(
                f"channels resolved to mismatched lengths: "
                f"{ {r: len(a) for r, a in out.items()} }"
            )
        return out

    def schema(self) -> Schema:
        return Schema(
            names=tuple(self._cols),
            kind="tabular",
            dtypes=tuple(str(a.dtype) for a in self._cols.values()),
            shape=(self.size() or 0, len(self._cols)),
        )

    def size(self) -> int | None:
        if not self._cols:
            return 0
        return int(len(next(iter(self._cols.values()))))

    def series(self, name: str) -> np.ndarray:
        try:
            return self._cols[name]
        except KeyError:
            raise KeyError(
                f"no column {name!r}; available: {list(self._cols)}"
            ) from None

    def extent(self, name: str) -> tuple[float, float] | None:
        return _numeric_extent(self.series(name))

    def select(self, names: Sequence[str]) -> EagerTabularRef:
        return EagerTabularRef(self._source, {n: self._cols[n] for n in names})

    def fingerprint(self):
        return id(self._source)

    def native(self) -> Any:
        return self._source


class EagerGriddedRef(GriddedRef):
    """In-memory gridded ref over a 2-D values array (+ optional axis coords)."""

    is_lazy = False

    def __init__(
        self,
        source: Any,
        values: np.ndarray,
        x: np.ndarray | None = None,
        y: np.ndarray | None = None,
    ) -> None:
        self._source = source
        self._values = np.asarray(values)
        self._x = x
        self._y = y

    def schema(self) -> Schema:
        return Schema(names=(), kind="gridded", shape=tuple(self._values.shape))

    def size(self) -> int | None:
        return int(self._values.size)

    def grid(self, value: str | None = None) -> GridData:
        v = self._values
        x = self._x if self._x is not None else np.arange(v.shape[-1])
        y = self._y if self._y is not None else np.arange(v.shape[0])
        return GridData(v, x, y)

    def fingerprint(self):
        return id(self._source)

    def native(self) -> Any:
        return self._source
