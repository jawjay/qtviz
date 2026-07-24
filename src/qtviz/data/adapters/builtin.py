"""Eager built-in adapters: dict, numpy, pandas, Arrow (spec §6.3).

pandas / pyarrow are detected via `sys.modules` so importing qtviz never
imports them — they are only present if the *user* already imported them to
build the object being wrapped.
"""

from __future__ import annotations

import sys
from typing import Any

import numpy as np

from ..ref import EagerGriddedRef, EagerTabularRef


def _reject_gridded(who: str, shape: str | None) -> None:
    if shape == "gridded":
        raise TypeError(f"{who} is tabular; cannot force gridded")


class DictAdapter:
    priority = 10

    def handles(self, obj: Any) -> bool:
        return isinstance(obj, dict)

    def wrap(self, obj: dict, shape: str | None = None) -> EagerTabularRef:
        _reject_gridded("a dict", shape)
        cols = {str(k): np.asarray(v) for k, v in obj.items()}
        return EagerTabularRef(obj, cols)


class NumpyAdapter:
    priority = 5

    def handles(self, obj: Any) -> bool:
        return isinstance(obj, np.ndarray)

    def wrap(self, obj: np.ndarray, shape: str | None = None):
        if shape == "gridded":
            return EagerGriddedRef(obj, obj)
        if obj.dtype.names:  # structured array → tabular
            return EagerTabularRef(obj, {n: obj[n] for n in obj.dtype.names})
        if shape == "tabular":
            raise TypeError("a plain ndarray has no column names; pass a dict or structured array")
        return EagerGriddedRef(obj, obj)  # plain array → gridded


class PandasAdapter:
    priority = 8

    def handles(self, obj: Any) -> bool:
        pd = sys.modules.get("pandas")
        return pd is not None and isinstance(obj, pd.DataFrame)

    def wrap(self, obj, shape: str | None = None) -> EagerTabularRef:
        _reject_gridded("a DataFrame", shape)
        cols = {str(c): np.asarray(obj[c].to_numpy()) for c in obj.columns}
        # The index joins the columns ([D73]) — a time-indexed frame plots
        # without reset_index(). A real data column always wins the name.
        index_name = str(obj.index.name) if obj.index.name is not None else "index"
        if index_name in cols:
            import warnings  # noqa: PLC0415

            from ...errors import QtvizWarning  # noqa: PLC0415

            warnings.warn(
                f"DataFrame index name {index_name!r} collides with a data column; "
                f"the column wins and the index is not exposed.",
                QtvizWarning,
                stacklevel=4,
            )
        else:
            cols[index_name] = np.asarray(obj.index.to_numpy())
        return EagerTabularRef(obj, cols)


class ArrowAdapter:
    priority = 8

    def handles(self, obj: Any) -> bool:
        pa = sys.modules.get("pyarrow")
        return pa is not None and isinstance(obj, pa.Table)

    def wrap(self, obj, shape: str | None = None) -> EagerTabularRef:
        _reject_gridded("an Arrow Table", shape)
        cols = {
            name: np.asarray(obj.column(name).to_numpy(zero_copy_only=False))
            for name in obj.column_names
        }
        return EagerTabularRef(obj, cols)


BUILTINS = (DictAdapter, NumpyAdapter, PandasAdapter, ArrowAdapter)
