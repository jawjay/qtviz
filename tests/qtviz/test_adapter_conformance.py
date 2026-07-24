"""Tier-1 — data-adapter conformance (milestone-data-core §5, step 3).

The keystone that pins the data contract: every tabular adapter, wrapping the
*same logical data*, must agree on schema, channel resolution (string /
Expression / callable accessors), size, and extent. Plus the laziness invariant:
`resolve_channels` reads only the columns the accessors reference (projection
pushdown), asserted with a counting namespace — no dask needed.

Parametrized over whatever containers import, so dask / xarray / zarr cases slot
in (steps 4–5) without touching this file.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
data = pytest.importorskip("qtviz.data")

from qtviz.data.accessor import resolve_accessor  # noqa: E402
from qtviz.data.ref import Schema, TabularRef  # noqa: E402

pytestmark = pytest.mark.tier1

# the reference logical data every adapter must reproduce
REF = {"a": np.arange(20.0), "b": np.arange(20.0) * 10.0, "c": np.arange(20.0) ** 2}


def _structured(d: dict) -> np.ndarray:
    n = len(next(iter(d.values())))
    arr = np.zeros(n, dtype=[(k, "float64") for k in d])
    for k, v in d.items():
        arr[k] = v
    return arr


class _CountingNamespace:
    """A name→array mapping that records which names were read."""

    def __init__(self, cols: dict) -> None:
        self._cols = cols
        self.read: set[str] = set()

    def __getitem__(self, name: str):
        self.read.add(name)
        return self._cols[name]


class LazyTrackingRef(TabularRef):
    """A lazy tabular ref that resolves through a counting namespace, so a test
    can assert pushdown — only referenced columns are touched."""

    is_lazy = True

    def __init__(self, cols: dict) -> None:
        self._cols = {k: np.asarray(v, dtype="float64") for k, v in cols.items()}
        self.ns = _CountingNamespace(self._cols)

    def schema(self) -> Schema:
        return Schema(names=tuple(self._cols), kind="tabular")

    def size(self):
        return len(next(iter(self._cols.values())))

    def extent(self, name):
        a = self._cols[name]
        return (float(a.min()), float(a.max()))

    def fingerprint(self):
        return id(self._cols)

    def native(self):
        return self.ns

    def resolve_channels(self, channels):
        return {r: resolve_accessor(a, columns=self.ns, native=self.ns)
                for r, a in channels.items()}


def _tabular_cases():
    cases = [
        ("dict", lambda d: data.as_data_ref(dict(d))),
        ("numpy_struct", lambda d: data.as_data_ref(_structured(d))),
        ("lazy_stub", lambda d: LazyTrackingRef(d)),
    ]
    try:
        import pandas as pd

        cases.append(("pandas", lambda d: data.as_data_ref(pd.DataFrame(d))))
    except ImportError:
        pass
    try:
        import pyarrow as pa

        cases.append(("arrow", lambda d: data.as_data_ref(pa.table(d))))
    except ImportError:
        pass
    try:
        import dask.dataframe as dd
        import pandas as pd

        def _dask(d):
            return data.as_data_ref(dd.from_pandas(pd.DataFrame(d), npartitions=2))

        cases.append(("dask", _dask))
    except ImportError:
        pass
    try:
        import xarray as xr

        def _xr(d):
            return data.as_data_ref(xr.Dataset({k: ("row", v) for k, v in d.items()}))

        cases.append(("xarray", _xr))
    except ImportError:
        pass
    return cases


@pytest.fixture(params=_tabular_cases(), ids=lambda c: c[0])
def ref(request):
    return request.param[1](REF)


# ── contract: every tabular adapter agrees ───────────────────────────────────
def test_is_tabular(ref):
    assert isinstance(ref, data.TabularRef)


def test_schema_names(ref):
    names = set(ref.schema().names)
    assert set(REF) <= names
    # the only sanctioned extra: pandas exposes its index as a column ([D73])
    assert names - set(REF) <= {"index"}


def test_size(ref):
    # lazy refs may report None (a row count would force a compute)
    assert ref.size() in (None, len(REF["a"]))


def test_extent(ref):
    extent = ref.extent("a")
    if extent is not None:  # best-effort; None is allowed for lazy refs
        lo, hi = extent
        assert lo == pytest.approx(0.0) and hi == pytest.approx(19.0)


def test_resolve_string_accessor(ref):
    np.testing.assert_allclose(ref.resolve_channels({"x": "a"})["x"], REF["a"])


def test_resolve_expression_accessor(ref):
    out = ref.resolve_channels({"y": qv.col("a") + qv.col("b")})["y"]
    np.testing.assert_allclose(out, REF["a"] + REF["b"])


def test_resolve_callable_accessor(ref):
    out = ref.resolve_channels({"y": lambda d: d["a"]})["y"]
    np.testing.assert_allclose(np.asarray(out, dtype="float64"), REF["a"])


def test_all_channel_kinds_together(ref):
    out = ref.resolve_channels({
        "x": "a",
        "y": qv.col("a") + qv.col("b"),
        "z": lambda d: d["c"],
    })
    np.testing.assert_allclose(out["x"], REF["a"])
    np.testing.assert_allclose(out["y"], REF["a"] + REF["b"])
    np.testing.assert_allclose(np.asarray(out["z"], dtype="float64"), REF["c"])


# ── laziness invariant: only referenced columns are read (pushdown) ──────────
def test_resolve_touches_only_referenced_columns():
    ref = LazyTrackingRef(REF)
    ref.resolve_channels({"x": "a", "y": qv.col("a") + qv.col("b")})
    assert ref.ns.read == {"a", "b"}  # never touched "c"


# ── gridded conformance: ndarray / xarray / dask.array / zarr agree ──────────
GREF = np.outer(np.arange(4.0), np.arange(5.0))


def _gridded_cases():
    cases = [("ndarray", lambda: data.as_data_ref(GREF))]
    try:
        import xarray as xr

        cases.append(("xarray2d", lambda: data.as_data_ref(xr.DataArray(GREF, dims=("y", "x")))))
    except ImportError:
        pass
    try:
        import dask.array as da

        cases.append(("dask_array", lambda: data.as_data_ref(da.from_array(GREF, chunks=(2, 5)))))
    except ImportError:
        pass
    try:
        import zarr

        cases.append(("zarr", lambda: data.as_data_ref(zarr.array(GREF, chunks=(2, 5)))))
    except ImportError:
        pass
    return cases


@pytest.fixture(params=_gridded_cases(), ids=lambda c: c[0])
def gridded_ref(request):
    return request.param[1]()


def test_is_gridded(gridded_ref):
    assert isinstance(gridded_ref, data.GriddedRef)


def test_grid_values_agree(gridded_ref):
    ref = gridded_ref if not gridded_ref.is_lazy else gridded_ref.materialize()
    np.testing.assert_allclose(np.asarray(ref.grid().values), GREF)
