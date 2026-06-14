"""dask adapter — out-of-core tabular + gridded data (D14/D17, milestone step 4).

The point of this adapter is to let qtviz *delegate* to dask rather than reinvent
it. Channel resolution applies each accessor to the dask collection — producing
lazy expressions — and computes them **together** in one `dask.compute` call, so:

- **projection pushdown** — only the columns the accessors reference are read
  (from Parquet, etc.); a 200-column frame plotted by x/y reads two columns;
- **shared subgraphs** — channels that reuse a derived column compute it once;
- **out-of-core / parallel** — dask's scheduler handles partitions and cores.

Metadata (`schema`, `fingerprint`) is cheap and never computes. `window` pushes a
row predicate down; `materialize` computes a (narrowed) collection to memory.
Nothing here imports dask at registration — only when an actual dask object is
wrapped — so the adapter is inert unless dask is in use.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..accessor import resolve_expr
from ..ref import EagerGriddedRef, EagerTabularRef, GriddedRef, Schema, TabularRef


def _checked(out: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    lengths = {len(a) for a in out.values()}
    if len(lengths) > 1:
        raise ValueError(
            f"channels resolved to mismatched lengths: { {r: len(a) for r, a in out.items()} }"
        )
    return out


class DaskTabularRef(TabularRef):
    is_lazy = True

    def __init__(self, ddf) -> None:
        self._ddf = ddf

    def schema(self) -> Schema:
        return Schema(
            names=tuple(str(c) for c in self._ddf.columns),
            kind="tabular",
            dtypes=tuple(str(d) for d in self._ddf.dtypes),
        )

    def size(self) -> int | None:
        return None  # row count needs a compute for a lazy frame — stay cheap

    def extent(self, name):
        return None  # best-effort; the backend auto-ranges on the materialized slice

    def fingerprint(self):
        import dask.base  # noqa: PLC0415

        return dask.base.tokenize(self._ddf)

    def native(self) -> Any:
        return self._ddf

    def subscribe(self, cb):
        from ...core.disposable import NOOP  # noqa: PLC0415

        return NOOP

    def select(self, names):
        return DaskTabularRef(self._ddf[list(names)])

    def window(self, **ranges):
        ddf = self._ddf
        for name, (lo, hi) in ranges.items():
            ddf = ddf[(ddf[name] >= lo) & (ddf[name] <= hi)]  # predicate pushdown
        return DaskTabularRef(ddf)

    def resolve_channels(self, channels):
        import dask  # noqa: PLC0415

        exprs = {role: resolve_expr(a, columns=self._ddf, native=self._ddf)
                 for role, a in channels.items()}
        roles = list(exprs)
        computed = dask.compute(*(exprs[r] for r in roles))  # one pass: pushdown + shared graph
        return _checked({r: np.asarray(v) for r, v in zip(roles, computed, strict=True)})

    def materialize(self, limit: int | None = None) -> EagerTabularRef:
        ddf = self._ddf if limit is None else self._ddf.head(limit, compute=False)
        pdf = ddf.compute()
        cols = {str(c): np.asarray(pdf[c].to_numpy()) for c in pdf.columns}
        return EagerTabularRef(pdf, cols)


class DaskGriddedRef(GriddedRef):
    is_lazy = True

    def __init__(self, arr, x=None, y=None) -> None:
        self._arr = arr
        self._x = x
        self._y = y

    def schema(self) -> Schema:
        return Schema(names=(), kind="gridded", shape=tuple(self._arr.shape))

    def size(self) -> int:
        return int(np.prod(self._arr.shape))  # shape is known cheaply for dask arrays

    def fingerprint(self):
        import dask.base  # noqa: PLC0415

        return dask.base.tokenize(self._arr)

    def native(self) -> Any:
        return self._arr

    def materialize(self, limit: int | None = None) -> EagerGriddedRef:
        return EagerGriddedRef(self._arr, np.asarray(self._arr.compute()), self._x, self._y)

    def grid(self, value: str | None = None):
        return self.materialize().grid(value)


class DaskAdapter:
    priority = 8

    def handles(self, obj: Any) -> bool:
        module = type(obj).__module__
        return module.startswith(("dask.dataframe", "dask.array", "dask_expr"))

    def wrap(self, obj: Any):
        if type(obj).__module__.startswith("dask.array"):
            return DaskGriddedRef(obj)
        return DaskTabularRef(obj)
