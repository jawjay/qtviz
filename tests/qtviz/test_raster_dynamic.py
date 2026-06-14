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
        return rgba, bounds

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
    c._on_done(c._build_id - 1, (np.zeros((1, 1, 4), np.uint8), (0, 0, 1, 1)), None)
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
    view = qv.View(qv.Scatter(data, x="x", y="y", scale="datashader"), backend="pyqtgraph")
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


def test_matplotlib_reaggregates_to_zoom_window(qtbot):
    pytest.importorskip("datashader")
    pytest.importorskip("matplotlib")
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib backend not registered")

    rng = np.random.default_rng(2)
    n = 50_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n)}
    view = qv.View(qv.Scatter(data, x="x", y="y", scale="datashader"), backend="matplotlib")
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
