"""xarray + zarr adapters and the shape-override escape hatches (D17, step 5).

Contract conformance lives in test_adapter_conformance.py (parametrized). Here:
shape selection (1-D vs N-D), the `qv.tabular()` / `qv.gridded()` overrides,
lazy (dask-backed / zarr) behavior, and one async render through the View.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
data = pytest.importorskip("qtviz.data")
xr = pytest.importorskip("xarray")
zarr = pytest.importorskip("zarr")

pytestmark = pytest.mark.tier1


# ── xarray shape selection (D17) ─────────────────────────────────────────────
def test_xarray_1d_dataarray_is_tabular():
    da = xr.DataArray(np.arange(10.0), dims=("t",), coords={"t": np.arange(10.0)}, name="v")
    ref = data.as_data_ref(da)
    assert isinstance(ref, data.TabularRef)
    np.testing.assert_allclose(ref.resolve_channels({"y": "v"})["y"], np.arange(10.0))
    np.testing.assert_allclose(ref.resolve_channels({"x": "t"})["x"], np.arange(10.0))


def test_xarray_2d_dataarray_is_gridded():
    da = xr.DataArray(np.arange(12.0).reshape(3, 4), dims=("y", "x"),
                      coords={"x": [10, 20, 30, 40]})
    ref = data.as_data_ref(da)
    assert isinstance(ref, data.GriddedRef)
    grid = ref.grid()
    assert np.asarray(grid.values).shape == (3, 4)
    np.testing.assert_array_equal(np.asarray(grid.x), [10, 20, 30, 40])


def test_dask_backed_xarray_is_lazy():
    da = xr.DataArray(np.arange(12.0).reshape(3, 4), dims=("y", "x")).chunk({"x": 2})
    assert data.as_data_ref(da).is_lazy


# ── zarr ─────────────────────────────────────────────────────────────────────
def test_zarr_is_lazy_gridded():
    z = zarr.array(np.outer(np.arange(4.0), np.arange(5.0)), chunks=(2, 5))
    ref = data.as_data_ref(z)
    assert isinstance(ref, data.GriddedRef) and ref.is_lazy and ref.size() == 20
    eager = ref.materialize()
    assert not eager.is_lazy
    np.testing.assert_allclose(np.asarray(eager.grid().values), np.asarray(z[:]))


# ── escape hatches (D17) ─────────────────────────────────────────────────────
def test_gridded_forces_shape():
    assert isinstance(qv.gridded(np.outer(np.arange(3.0), np.arange(4.0))), data.GriddedRef)
    # force a 1-D DataArray (default tabular) to gridded
    da = xr.DataArray(np.arange(6.0), dims=("t",))
    assert isinstance(qv.gridded(da), data.GriddedRef)


def test_tabular_forces_shape():
    # force a 2-D DataArray (default gridded) to tabular
    da = xr.DataArray(np.arange(12.0).reshape(3, 4), dims=("y", "x"))
    assert isinstance(qv.tabular(da), data.TabularRef)


def test_shape_override_rejects_impossible():
    with pytest.raises(TypeError):
        qv.gridded({"a": [1, 2, 3]})           # a dict can't be gridded
    with pytest.raises(TypeError):
        qv.tabular(np.zeros((3, 4)))           # a plain ndarray has no column names


# ── async render through the View (Tier 2) ───────────────────────────────────
@pytest.mark.tier2
def test_zarr_image_renders_async(qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    z = zarr.array(np.outer(np.hanning(30), np.hanning(40)), chunks=(15, 40))
    view = qv.View(qv.Image(z, bounds=(0, 0, 40, 30)), backend="pyqtgraph")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=5000)
    assert view.handle is not None
