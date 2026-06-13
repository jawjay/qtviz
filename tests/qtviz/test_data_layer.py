"""Tier-1 + Tier-3 — the data layer (spec §2.1 + §6).

The contract that lets one Element bind to dict / pandas / Arrow today and
xarray / zarr / dask later, and render without materializing more than the
visible slice. The conformance test (`dict ≡ pandas ≡ arrow`) is the
executable form of "adding a container is one adapter file".
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
data = pytest.importorskip("qtviz.data")

pytestmark = pytest.mark.tier1


# ── contract: tabular ────────────────────────────────────────────────────────
def test_as_data_ref_is_idempotent(table):
    ref = data.as_data_ref(table)
    assert data.as_data_ref(ref) is ref


def test_dict_wraps_to_tabular_ref(table):
    ref = data.as_data_ref(table)
    assert isinstance(ref, data.TabularRef)
    assert ref.is_lazy is False


def test_series_returns_1d_numpy(table):
    ref = data.as_data_ref(table)
    s = ref.series("x")
    assert isinstance(s, np.ndarray)
    assert s.ndim == 1 and len(s) == len(table["x"])
    np.testing.assert_array_equal(s, table["x"])


def test_schema_lists_names_cheaply(table):
    schema = data.as_data_ref(table).schema()
    names = set(getattr(schema, "names", schema))
    assert {"x", "y", "z"} <= names


def test_size_is_row_count(table):
    assert data.as_data_ref(table).size() == len(table["x"])


def test_materialize_is_identity_for_eager(table):
    ref = data.as_data_ref(table)
    mat = ref.materialize()
    assert mat.is_lazy is False
    np.testing.assert_array_equal(mat.series("y"), table["y"])


def test_select_narrows_but_preserves_access(table):
    ref = data.as_data_ref(table).select(["x", "y"])
    assert isinstance(ref, data.DataRef)
    np.testing.assert_array_equal(ref.series("x"), table["x"])


def test_window_returns_a_dataref(table):
    ref = data.as_data_ref(table)
    assert isinstance(ref.window(x=(2.0, 8.0)), data.DataRef)


def test_native_round_trips_underlying(table):
    assert data.as_data_ref(table).native() is not None


# ── contract: fingerprint (drives Element value identity, §2.1) ──────────────
def test_fingerprint_is_cheap_stable_and_hashable(table):
    ref = data.as_data_ref(table)
    fp = ref.fingerprint()
    assert hash(fp) == hash(ref.fingerprint())            # stable + hashable


def test_fingerprint_distinguishes_data_objects(table):
    other = {k: v.copy() for k, v in table.items()}
    assert data.as_data_ref(table).fingerprint() != data.as_data_ref(other).fingerprint()


# ── contract: gridded ────────────────────────────────────────────────────────
def test_ndarray_wraps_to_gridded_ref(grid):
    values, bounds = grid
    ref = data.as_data_ref(values)
    assert isinstance(ref, data.GriddedRef)
    g = ref.grid()
    gv = getattr(g, "values", g[0] if isinstance(g, tuple) else g)
    assert np.asarray(gv).ndim == 2


# ── Tier-3 — adapter conformance: every tabular encoding agrees ──────────────
@pytest.mark.conformance
def test_tabular_adapters_agree(tabular_encoding, table):
    enc, obj = tabular_encoding
    ref = data.as_data_ref(obj)
    assert isinstance(ref, data.TabularRef), enc
    for col in ("x", "y", "z"):
        np.testing.assert_allclose(np.asarray(ref.series(col)), table[col], err_msg=enc)


# ── Tier-3 — laziness: narrow before you pull (spec §6.2) ────────────────────
@pytest.mark.conformance
def test_lazy_adapter_does_not_compute_on_narrowing():
    """A lazy container (dask) must report is_lazy, answer metadata cheaply,
    and only become eager on materialize(). Activates once the dask adapter
    is registered."""
    da = pytest.importorskip("dask.array")
    pytest.importorskip("qtviz.data.adapters.dask")  # skip until the adapter lands
    arr = da.ones((10_000, 3), chunks=(1000, 3))
    ref = data.as_data_ref(arr)
    assert ref.is_lazy is True
    assert ref.size() is not None              # metadata, no compute
    narrowed = ref.window()                    # pushdown, still lazy
    assert narrowed.is_lazy is True
    assert ref.materialize().is_lazy is False  # the only place compute happens
