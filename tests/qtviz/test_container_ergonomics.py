"""0.5 increment 1 — container ergonomics ([D73], milestone-0.5-array-core §1).

The five focus containers (numpy / pandas / dask / zarr / xarray) wrap with
less friction: the pandas index becomes a plottable column, a zarr Group of
1-D arrays is a table, a one-variable xarray Dataset can be gridded, and
xarray extents come from the (cheap, eager) coords.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.data import as_data_ref  # noqa: E402
from qtviz.errors import AdapterError, QtvizWarning  # noqa: E402

pytestmark = pytest.mark.tier1


# ── pandas: the index is a column ────────────────────────────────────────────
def test_pandas_named_index_is_a_column():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"temp": [1.0, 2.0, 3.0]},
                      index=pd.Index([10.0, 20.0, 30.0], name="t"))
    ref = as_data_ref(df)
    assert "t" in ref.schema().names
    assert np.allclose(ref.series("t"), [10.0, 20.0, 30.0])
    # the everyday win: a time-indexed frame plots without reset_index()
    el = qv.Curve(df, x="t", y="temp")
    assert el.data.schema().names  # constructed + validated


def test_pandas_unnamed_index_is_named_index():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"v": [1.0, 2.0]})
    ref = as_data_ref(df)
    assert "index" in ref.schema().names
    assert np.allclose(ref.series("index"), [0, 1])


def test_pandas_index_never_shadows_a_real_column():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"t": [1.0, 2.0]}, index=pd.Index([9.0, 9.0], name="t"))
    with pytest.warns(QtvizWarning, match="index"):
        ref = as_data_ref(df)
    assert np.allclose(ref.series("t"), [1.0, 2.0])  # the data column wins


# ── zarr: a Group of 1-D arrays is a table ───────────────────────────────────
def _zarr_group():
    zarr = pytest.importorskip("zarr")
    g = zarr.group()
    g["t"] = np.arange(5, dtype="float64")
    g["v"] = np.arange(5, dtype="float64") * 2
    return g


def test_zarr_group_wraps_tabular():
    g = _zarr_group()
    ref = as_data_ref(g)
    assert ref.schema().kind == "tabular"
    assert set(ref.schema().names) == {"t", "v"}
    el = qv.Curve(g, x="t", y="v")
    assert el.data.size() == 5


def test_zarr_group_rejects_ragged_and_nd_members():
    zarr = pytest.importorskip("zarr")
    ragged = zarr.group()
    ragged["a"] = np.arange(3, dtype="float64")
    ragged["b"] = np.arange(4, dtype="float64")
    with pytest.raises(AdapterError, match="length"):
        as_data_ref(ragged)
    nd = zarr.group()
    nd["m"] = np.zeros((2, 2))
    with pytest.raises(AdapterError, match="1-D"):
        as_data_ref(nd)


def test_zarr_array_still_gridded():
    zarr = pytest.importorskip("zarr")
    z = zarr.array(np.zeros((4, 4)))
    assert as_data_ref(z).schema().kind == "gridded"


# ── xarray: one-var Dataset gridding + coord extents ─────────────────────────
def _dataset(nvars=1):
    xr = pytest.importorskip("xarray")
    data = {"temp": (("y", "x"), np.arange(12.0).reshape(3, 4))}
    if nvars > 1:
        data["salinity"] = (("y", "x"), np.ones((3, 4)))
    return xr.Dataset(data, coords={"x": np.linspace(0.0, 30.0, 4),
                                    "y": np.linspace(-5.0, 5.0, 3)})


def test_gridded_single_var_dataset_selects_the_var():
    ref = qv.gridded(_dataset())
    assert ref.schema().kind == "gridded" and ref.schema().shape == (3, 4)
    grid = ref.grid()
    assert np.allclose(grid.x, [0.0, 10.0, 20.0, 30.0])   # real coords, not arange


def test_gridded_multi_var_dataset_errors_naming_vars():
    with pytest.raises(TypeError, match="salinity"):
        qv.gridded(_dataset(nvars=2))


def test_xarray_gridded_extent_from_coords_without_compute():
    xr = pytest.importorskip("xarray")
    da = _dataset()["temp"]
    ref = as_data_ref(da)
    assert ref.extent("x") == (0.0, 30.0)
    assert ref.extent("y") == (-5.0, 5.0)
    assert ref.extent("nope") is None
    # dask-backed: extent still must not compute the values
    dask = pytest.importorskip("dask.array")
    lazy = xr.DataArray(dask.from_array(np.zeros((3, 4)), chunks=2),
                        dims=("y", "x"),
                        coords={"x": np.arange(4.0), "y": np.arange(3.0)})
    assert as_data_ref(lazy).extent("x") == (0.0, 3.0)
