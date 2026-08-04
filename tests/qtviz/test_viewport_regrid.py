"""0.5 increment 3 — viewport regrid ([D75], milestone-0.5 §3).

`window()` gives lazy gridded refs strictly-partial reads; `regrid()` windows +
decimates + shades the visible region at widget resolution; the render path
wires it through the same `RasterController` the datashader loop uses — a huge
grid sharpens on zoom instead of pixelating.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.data import as_data_ref  # noqa: E402
from qtviz.data.regrid import make_regrid  # noqa: E402

from .test_gridded_decimation import _big_zarr  # noqa: E402  (counting store)


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


# ── Tier-1: window() narrows each container ──────────────────────────────────
@pytest.mark.tier1
def test_zarr_window_reads_only_in_window_chunks():
    z, store = _big_zarr(shape=(2048, 2048), chunks=(256, 256))
    ref = as_data_ref(z)
    win = ref.window(x=(0, 256), y=(0, 256))
    assert win.is_lazy
    assert win.schema().shape[:2] == (256, 256)
    store.gets = 0
    eager = win.materialize()
    assert eager.grid().values.shape == (256, 256)
    assert store.gets == 1                          # strictly partial I/O: 1 of 64
    # coords are absolute source indices, so geometry stays anchored
    assert eager.grid().x[0] == 0 and eager.grid().y[-1] == 255


@pytest.mark.tier1
def test_dask_and_xarray_window_narrow_lazily():
    da = pytest.importorskip("dask.array")
    arr = da.zeros((1000, 1000), chunks=100)
    win = as_data_ref(arr).window(x=(100, 300), y=(0, 50))
    assert win.is_lazy and win.schema().shape == (50, 200)

    xr = pytest.importorskip("xarray")
    xda = xr.DataArray(np.zeros((100, 200)), dims=("y", "x"))
    xwin = as_data_ref(xda).window(x=(10, 60), y=(20, 40))
    assert xwin.schema().shape == (20, 50)


# ── Tier-1: regrid maps the viewport, shades, and stays truthful ─────────────
@pytest.mark.tier1
def test_regrid_windows_decimates_and_shades():
    from qtviz.core.palette import palettes

    z, store = _big_zarr(shape=(2048, 2048), chunks=(256, 256))
    ref = as_data_ref(z)
    bounds = (0.0, 0.0, 10.0, 10.0)                 # the Image's data-space bounds
    rasterize = make_regrid(bounds, palettes.get("viridis"), title="temp")
    store.gets = 0
    result = rasterize(ref, width=100, height=100,
                       x_range=(0.0, 2.5), y_range=(0.0, 2.5))  # bottom-left quarter
    assert result.rgba.shape[2] == 4 and result.rgba.dtype == np.uint8
    assert result.rgba.shape[0] * result.rgba.shape[1] <= 100 * 100 * 4
    assert store.gets < 64                          # only the visible quarter read
    x0, y0, x1, y1 = result.bounds                  # window bounds, data space
    assert x0 == 0.0 and y0 == 0.0 and x1 <= 2.6 and y1 <= 2.6
    # legend is truthful for the VISIBLE window (rows 0..~512 → values 0..~512)
    assert result.legend.vmin == 0.0
    assert 400 <= result.legend.vmax <= 520
    assert result.legend.title == "temp"


@pytest.mark.tier1
def test_regrid_clamps_out_of_bounds_viewport():
    from qtviz.core.palette import palettes

    z, _ = _big_zarr(shape=(256, 256), chunks=(64, 64))
    rasterize = make_regrid((0.0, 0.0, 1.0, 1.0), palettes.get("viridis"))
    result = rasterize(as_data_ref(z), width=50, height=50,
                       x_range=(-5.0, 5.0), y_range=(0.9, 7.0))  # mostly outside
    assert result.rgba.size > 0                     # clamped, not crashed


# ── Tier-2: the render path wires the loop ───────────────────────────────────
def _lazy_image(qtbot, backend):
    z, store = _big_zarr(shape=(2048, 2048), chunks=(256, 256))
    el = qv.Image(z, extent=(0.0, 0.0, 10.0, 10.0))
    view = qv.View(el, backend=backend)
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()  # offscreen-safe; gives the ViewBox a real pixel geometry
    qtbot.waitUntil(lambda: view.handle is not None, timeout=5000)  # lazy → async
    return view, el, store


@pytest.mark.tier2
def test_pyqtgraph_lazy_grid_renders_shaded_with_legend_and_controller(qtbot):
    view, el, _ = _lazy_image(qtbot, "pyqtgraph")
    item = view.native(el.id)
    assert np.asarray(item.image).ndim == 3         # shaded rgba, not raw floats
    plot = view.handle.plots[0]
    assert getattr(plot, "_qtviz_cbar", None) is not None      # value colorbar
    vb = plot.getViewBox()
    assert getattr(vb, "_qtviz_rasters", [])        # regrid controller wired


@pytest.mark.tier2
def test_pyqtgraph_zoom_regrids_to_the_window(qtbot):
    view, el, store = _lazy_image(qtbot, "pyqtgraph")
    vb = view.handle.plots[0].getViewBox()
    item = view.native(el.id)
    store.gets = 0
    vb.setXRange(0.0, 1.0, padding=0)               # zoom to the left tenth
    vb.setYRange(0.0, 1.0, padding=0)

    def narrowed():
        rect = item.mapRectToParent(item.boundingRect())  # data-space rect
        return rect.width() < 5.0                   # raster re-bounded to ~the window

    qtbot.waitUntil(narrowed, timeout=5000)
    assert store.gets > 0                           # a real partial re-read happened


@pytest.mark.tier2
def test_matplotlib_lazy_grid_renders_shaded_and_wired(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view, el, _ = _lazy_image(qtbot, "matplotlib")
    ax = view.handle.axes[0]
    assert getattr(ax, "_qtviz_rasters", [])        # controller wired
    assert np.asarray(view.native(el.id).get_array()).ndim == 3  # shaded rgba


@pytest.mark.tier2
def test_milestone_0_5_acceptance(qtbot):
    """milestone-0.5 §9 end to end: a 16k×16k zarr (256M cells — never written,
    so only touched chunks cost anything) renders decimated after reading a tiny
    fraction of its chunks; zoom re-reads only the visible window and the raster
    sharpens; a dask-backed xarray field takes the same path."""
    zarr = pytest.importorskip("zarr")
    from qtviz.data.adapters.zarr import ZarrGriddedRef  # noqa: PLC0415

    from .test_gridded_decimation import _CountingStore  # noqa: PLC0415

    store = _CountingStore()
    z = zarr.create_array(store=store, shape=(16_384, 16_384), chunks=(512, 512),
                          dtype="f8")                  # unwritten → fill-value reads
    el = qv.Image(z, extent=(0.0, 0.0, 100.0, 100.0))
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    item = view.native(el.id)
    assert np.asarray(item.image).size <= 4 * 800 * 600 * 4  # memory-bounded (rgba)
    vb = view.handle.plots[0].getViewBox()
    store.gets = 0
    vb.setXRange(0.0, 5.0, padding=0)                   # zoom to 1/20th per axis
    vb.setYRange(0.0, 5.0, padding=0)
    qtbot.waitUntil(
        lambda: item.mapRectToParent(item.boundingRect()).width() < 20.0, timeout=5000
    )
    # the zoom re-read is strictly partial: only in-window chunks (~2×2 of 32×32)
    assert 0 < store.gets <= 16
    # dask-backed xarray grid takes the same loop
    dask_array = pytest.importorskip("dask.array")
    xr = pytest.importorskip("xarray")
    da = xr.DataArray(dask_array.zeros((4096, 4096), chunks=512), dims=("y", "x"))
    el2 = qv.Image(da, extent=(0.0, 0.0, 1.0, 1.0))
    v2 = qv.View(el2, backend="pyqtgraph")
    qtbot.addWidget(v2)
    v2.resize(400, 300)
    v2.show()
    qtbot.waitUntil(lambda: v2.handle is not None, timeout=8000)
    assert getattr(v2.handle.plots[0].getViewBox(), "_qtviz_rasters", [])
    assert isinstance(as_data_ref(z), ZarrGriddedRef)   # (import used)


@pytest.mark.tier2
def test_small_eager_grid_regression(qtbot):
    """Under-budget / eager grids render exactly as before — raw values, no loop."""
    el = qv.Image(np.arange(16.0).reshape(4, 4), extent=(0.0, 0.0, 1.0, 1.0))
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    item = view.native(el.id)
    assert np.asarray(item.image).ndim == 2         # raw values, default LUT
    assert not getattr(view.handle.plots[0].getViewBox(), "_qtviz_rasters", [])
