"""Dynamic viewport re-aggregation — the 4b datashader loop (D21).

The controller re-rasterizes the source to the visible viewport at the widget's
pixel size as the user pans/zooms. These tests cover the backend-agnostic
controller with a fake target (no datashader / no backend needed), plus an
end-to-end zoom on the pyqtgraph backend.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.disposable import Disposable  # noqa: E402
from qtviz.core.raster import RasterController  # noqa: E402
from qtviz.ext.datashader import RasterAggregate, RasterResult  # noqa: E402

pytestmark = pytest.mark.tier2


class FakeTarget:
    """A RasterTarget that records writes and lets the test fire viewport changes."""

    def __init__(self, vp=((0.0, 1.0), (0.0, 1.0)), size=(100, 80)) -> None:
        self._vp = vp
        self._size = size
        self._cb = None
        self.writes: list = []  # (rgba, bounds)

    def viewport(self):
        return self._vp

    def pixel_size(self):
        return self._size

    def set_raster(self, rgba, bounds) -> None:
        self.writes.append((rgba, bounds))

    def connect_viewport(self, cb) -> Disposable:
        self._cb = cb
        return Disposable(lambda: setattr(self, "_cb", None))

    def fire(self) -> None:
        if self._cb is not None:
            self._cb()


def _recorder(calls):
    def rasterize(_source, *, width, height, x_range, y_range):
        calls.append((width, height, x_range, y_range))
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        bounds = (x_range[0], y_range[0], x_range[1], y_range[1])
        agg = RasterAggregate(np.zeros((height, width)), bounds, "count")
        return RasterResult(rgba, bounds, agg)

    return rasterize


def test_renders_once_at_widget_resolution_on_init(qtbot):
    target = FakeTarget(vp=((2.0, 4.0), (0.0, 1.0)), size=(120, 90))
    calls: list = []
    RasterController(source=object(), target=target, rasterize=_recorder(calls), debounce_ms=10)
    qtbot.waitUntil(lambda: bool(target.writes), timeout=2000)
    # aggregated to the target's pixel size at its current viewport
    assert calls[-1] == (120, 90, (2.0, 4.0), (0.0, 1.0))


def test_reaggregates_on_viewport_change(qtbot):
    target = FakeTarget(vp=((0.0, 10.0), (0.0, 10.0)), size=(100, 100))
    calls: list = []
    c = RasterController(source=object(), target=target, rasterize=_recorder(calls), debounce_ms=10)
    qtbot.waitUntil(lambda: bool(target.writes), timeout=2000)
    n = len(calls)
    target._vp = ((1.0, 2.0), (3.0, 4.0))  # user zoomed in
    target.fire()
    qtbot.waitUntil(lambda: len(calls) > n, timeout=2000)
    assert calls[-1] == (100, 100, (1.0, 2.0), (3.0, 4.0))
    c.dispose()


def test_debounces_a_burst_into_one_aggregation(qtbot):
    target = FakeTarget()
    calls: list = []
    c = RasterController(source=object(), target=target, rasterize=_recorder(calls), debounce_ms=80)
    qtbot.waitUntil(lambda: bool(target.writes), timeout=2000)
    n = len(calls)
    for _ in range(6):  # rapid pan/zoom
        target.fire()
    qtbot.wait(250)
    assert len(calls) == n + 1  # six changes collapsed to one re-aggregation
    c.dispose()


def test_drops_stale_results(qtbot):
    target = FakeTarget()
    c = RasterController(source=object(), target=target, rasterize=_recorder([]), debounce_ms=10)
    qtbot.waitUntil(lambda: bool(target.writes), timeout=2000)
    before = len(target.writes)
    # a result tagged with a superseded build-id must not paint
    stale = RasterResult(np.zeros((1, 1, 4), np.uint8), (0, 0, 1, 1),
                         RasterAggregate(np.zeros((1, 1)), (0, 0, 1, 1), "count"))
    c._on_done(c._build_id - 1, stale, None)
    assert len(target.writes) == before
    c.dispose()


def test_dispose_unsubscribes_and_halts(qtbot):
    target = FakeTarget()
    calls: list = []
    c = RasterController(source=object(), target=target, rasterize=_recorder(calls), debounce_ms=10)
    qtbot.waitUntil(lambda: bool(target.writes), timeout=2000)
    c.dispose()
    assert target._cb is None  # unsubscribed
    n = len(calls)
    target.fire()  # no-op: callback was removed; even if invoked, controller is disposed
    qtbot.wait(80)
    assert len(calls) == n


# ── end-to-end on the pyqtgraph backend ──────────────────────────────────────
def test_pyqtgraph_reaggregates_to_zoom_window(qtbot):
    pytest.importorskip("datashader")
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    import pyqtgraph as pg

    rng = np.random.default_rng(1)
    n = 50_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n)}
    view = qv.View(qv.Scatter(data, x="x", y="y", raster="datashader"), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)

    plot = view.handle.plots[0]
    vb = plot.getViewBox()
    qtbot.waitUntil(lambda: getattr(vb, "_qtviz_rasters", None) is not None, timeout=4000)
    img = next(it for it in plot.items if isinstance(it, pg.ImageItem))

    def raster_left() -> float:
        r = img.mapRectToView(img.boundingRect())  # raster extent in data coords
        return r.left()

    # initially the raster spans the full data extent (≈ -4.x)
    qtbot.waitUntil(lambda: raster_left() < -2.0, timeout=6000)

    vb.setRange(xRange=(-0.5, 0.5), yRange=(-0.5, 0.5), padding=0)  # zoom in
    # the controller re-aggregates to the visible window → raster extent shrinks
    qtbot.waitUntil(lambda: abs(raster_left() - (-0.5)) < 0.25, timeout=6000)



# ── autorange drift (P2 bug, roadmap-post-rerun §2) ──────────────────────────
# After a re-aggregation the raster always fills the (padded) viewport, so if
# the image item keeps feeding autorange, every autorange pass pads the raster's
# rect *again* — a runaway ~6%/cycle zoom-out on pyqtgraph. matplotlib drifted
# the other way: `set_extent` under autoscale snaps the limits to the raster's
# pixel-center extent (half a pixel inside the viewport), a slow zoom-in.
# These drive the real per-backend targets synchronously — one set_raster +
# autorange pass per cycle, no worker threads — so the loop is deterministic.


def test_pg_raster_does_not_feed_autorange_after_first_write(qtbot):
    pg = pytest.importorskip("pyqtgraph")
    from PySide6.QtCore import QRectF

    from qtviz.backends.pyqtgraph._raster import PgRasterTarget

    plot = pg.PlotWidget()
    qtbot.addWidget(plot)
    vb = plot.getViewBox()
    item = pg.ImageItem(np.zeros((8, 8, 4), dtype=np.uint8), axisOrder="row-major")
    plot.addItem(item)
    item.setRect(QRectF(0.0, 0.0, 10.0, 10.0))
    vb.updateAutoRange()  # initial framing: the static raster + padding
    target = PgRasterTarget(item, vb)

    (x0, x1), _ = vb.viewRange()
    span0 = x1 - x0
    assert span0 > 10.0  # framed with padding — autorange saw the static raster
    for _ in range(8):
        (x0, x1), (y0, y1) = vb.viewRange()
        # what the controller writes after re-aggregating: raster == viewport
        target.set_raster(np.zeros((8, 8, 4), dtype=np.uint8), (x0, y0, x1, y1))
        vb.updateAutoRange()  # what the next paint pass does
    (nx0, nx1), _ = vb.viewRange()
    assert abs((nx1 - nx0) / span0 - 1.0) < 0.01  # held (was ×1.06 per cycle)


def test_mpl_raster_updates_leave_limits_and_datalim_alone():
    pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure

    from qtviz.backends.matplotlib._raster import MplRasterTarget

    fig = Figure()
    ax = fig.add_subplot()
    img = ax.imshow(np.zeros((8, 8, 4)), extent=(0.0, 10.0, 0.0, 10.0),
                    origin="lower", aspect="auto")
    ax.autoscale(True)
    ax.set_xlim(0.0, 10.0)
    ax.set_ylim(0.0, 10.0)
    ax.set_autoscalex_on(True)
    ax.set_autoscaley_on(True)
    target = MplRasterTarget(img, ax)

    datalim0 = ax.dataLim.get_points().copy()
    for _ in range(8):
        (x0, x1), (y0, y1) = target.viewport()
        dx, dy = (x1 - x0) / 100.0, (y1 - y0) / 100.0
        # datashader bounds sit at pixel centers — half a pixel inside the view
        target.set_raster(np.zeros((8, 8, 4), dtype=np.uint8),
                          (x0 + dx / 2, y0 + dy / 2, x1 - dx / 2, y1 - dy / 2))
    assert ax.get_xlim() == (0.0, 10.0)  # held (drifted inward before the fix)
    assert ax.get_ylim() == (0.0, 10.0)
    np.testing.assert_allclose(ax.dataLim.get_points(), datalim0)  # not polluted
    assert ax.get_autoscalex_on() and ax.get_autoscaley_on()  # state preserved


def test_pg_streaming_datashaded_view_holds_viewport(qtbot):
    """Roadmap acceptance (bounded): a streaming datashaded view holds its
    viewport across append → re-aggregate → autorange cycles."""
    pytest.importorskip("datashader")
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")

    rng = np.random.default_rng(3)
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=rng.normal(0, 1, 5000), v=rng.normal(0, 1, 5000))
    el = qv.Scatter(feed, x="t", y="v", raster="datashader")
    handle = qv.backends.get("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    handle.widget.resize(600, 400)
    handle.widget.show()
    vb = handle.plots[0].getViewBox()
    controller = next(c for c in vb._qtviz_rasters if getattr(c, "element_id", None) == el.id)

    # settle: layout + initial framing of the static raster (span ≈ data extent)
    qtbot.waitUntil(lambda: vb.viewRange()[0][1] - vb.viewRange()[0][0] > 2.0, timeout=5000)
    vb.updateAutoRange()
    (x0, x1), _ = vb.viewRange()
    span0 = x1 - x0
    for _ in range(4):
        builds = controller._build_id
        feed.append(t=rng.normal(0, 1, 200), v=rng.normal(0, 1, 200))
        assert handle.set_element_data(el.id, {"t": np.empty(0), "v": np.empty(0)}) is True
        qtbot.waitUntil(lambda b=builds: controller._build_id > b, timeout=5000)
        qtbot.wait(50)  # let the queued set_raster land
        vb.updateAutoRange()  # the paint-time pass that compounded the drift
    (nx0, nx1), _ = vb.viewRange()
    assert abs((nx1 - nx0) / span0 - 1.0) < 0.01
    handle.dispose()


def test_matplotlib_reaggregates_to_zoom_window(qtbot):
    pytest.importorskip("datashader")
    pytest.importorskip("matplotlib")
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib backend not registered")

    rng = np.random.default_rng(2)
    n = 50_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n)}
    view = qv.View(qv.Scatter(data, x="x", y="y", raster="datashader"), backend="matplotlib")
    qtbot.addWidget(view)
    view.resize(600, 400)
    view.show()
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)

    ax = view.handle.axes[0]
    qtbot.waitUntil(lambda: getattr(ax, "_qtviz_rasters", None) is not None, timeout=4000)
    img = ax.images[0]

    def raster_left() -> float:
        return img.get_extent()[0]

    qtbot.waitUntil(lambda: raster_left() < -2.0, timeout=6000)  # full extent first

    ax.set_xlim(-0.5, 0.5)  # zoom triggers the lim callbacks
    ax.set_ylim(-0.5, 0.5)
    qtbot.waitUntil(lambda: abs(raster_left() - (-0.5)) < 0.25, timeout=6000)
