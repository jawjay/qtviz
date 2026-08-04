"""Raster reverse-lookup — hover/inspect value on a datashaded view ([D46]).

The datashader path computes a per-pixel aggregate (count/mean) but historically
discarded it. This retains it as a `RasterAggregate` (pure, Tier-1) carried on a
`RasterResult`, threads it through the static + dynamic (4b) paths, and surfaces
the value under the cursor as `HoverEvent.value`.

Spec: `milestone-raster-inspect.md`. Tier-1 covers the pure pixel→value mapping and
aggregate retention; Tier-2 covers freshness through the controller and end-to-end
hover on each native backend.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

# RasterAggregate/RasterResult are pure (numpy only; datashader imported lazily for
# the aggregation), so the value-mapping tests need no datashader.
from qtviz.ext.datashader import RasterAggregate, RasterResult  # noqa: E402

# ════════════════════════ Tier 1 — RasterAggregate.value_at ════════════════════
# values[0] is the ymin row (origin lower-left), matching the RGBA raster.


@pytest.mark.tier1
def test_value_at_maps_each_cell():
    agg = RasterAggregate(
        values=np.array([[1.0, 2.0], [3.0, 4.0]]),  # row0=ymin, row1=ymax
        bounds=(0.0, 0.0, 2.0, 2.0),  # RasterAggregate keeps its internal naming
        kind="count",
    )
    assert agg.value_at(0.5, 0.5) == 1.0   # x col0, y row0 (ymin)
    assert agg.value_at(1.5, 0.5) == 2.0   # x col1, y row0
    assert agg.value_at(0.5, 1.5) == 3.0   # x col0, y row1 (ymax)
    assert agg.value_at(1.5, 1.5) == 4.0


@pytest.mark.tier1
def test_value_at_clamps_upper_edge():
    agg = RasterAggregate(np.array([[1.0, 2.0], [3.0, 4.0]]), (0.0, 0.0, 2.0, 2.0), "count")
    assert agg.value_at(2.0, 2.0) == 4.0   # exact max edge → last cell, not out of range


@pytest.mark.tier1
def test_value_at_out_of_bounds_is_none():
    agg = RasterAggregate(np.array([[1.0, 2.0], [3.0, 4.0]]), (0.0, 0.0, 2.0, 2.0), "count")
    assert agg.value_at(-0.1, 1.0) is None
    assert agg.value_at(1.0, 2.5) is None


@pytest.mark.tier1
def test_value_at_empty_pixel_is_none():
    # count: an empty pixel is 0 → nothing to inspect
    agg = RasterAggregate(np.array([[0.0, 2.0], [3.0, 4.0]]), (0.0, 0.0, 2.0, 2.0), "count")
    assert agg.value_at(0.5, 0.5) is None
    assert agg.value_at(1.5, 0.5) == 2.0


@pytest.mark.tier1
def test_value_at_nan_pixel_is_none():
    # mean: an empty pixel is NaN
    agg = RasterAggregate(np.array([[math.nan, 2.0], [3.0, 4.0]]), (0.0, 0.0, 2.0, 2.0), "mean")
    assert agg.value_at(0.5, 0.5) is None


@pytest.mark.tier1
def test_value_at_degenerate_bounds_is_none():
    agg = RasterAggregate(np.array([[1.0]]), (1.0, 1.0, 1.0, 1.0), "count")
    assert agg.value_at(1.0, 1.0) is None  # zero-width extent, no mapping


# ════════════════════════ Tier 1 — aggregate retention ═════════════════════════
@pytest.mark.tier1
def test_rasterize_element_retains_aggregate():
    pytest.importorskip("datashader")
    from qtviz.ext.datashader import rasterize_element

    cluster = {"x": np.r_[np.full(5000, 1.0), np.full(50, 9.0)],
               "y": np.r_[np.full(5000, 1.0), np.full(50, 9.0)]}
    result = rasterize_element(qv.Scatter(cluster, x="x", y="y"), width=40, height=30)
    assert isinstance(result, RasterResult)
    assert result.rgba.shape == (30, 40, 4)
    agg = result.aggregate
    assert agg.values.shape == (30, 40)
    assert agg.kind == "count"
    # query via the aggregate's own (bin-center) bounds: dense cluster near the min
    # corner, sparse near the max corner.
    xmin, ymin, xmax, ymax = agg.bounds
    dense, sparse = agg.value_at(xmin, ymin), agg.value_at(xmax, ymax)
    assert dense is not None and sparse is not None and dense > sparse


# ════════════════════════ Tier 2 — freshness through the controller ════════════
@pytest.mark.tier2
def test_controller_pushes_fresh_aggregate(qtbot):
    """On (re)aggregation the controller hands the new aggregate to on_aggregate on
    the GUI thread; a stale build-id must not update it."""
    from qtviz.core.disposable import Disposable
    from qtviz.core.raster import RasterController

    class FakeTarget:
        def __init__(self):
            self._cb = None
            self.writes = []
        def viewport(self):
            return (0.0, 1.0), (0.0, 1.0)
        def pixel_size(self):
            return (4, 4)
        def set_raster(self, rgba, bounds):
            self.writes.append((rgba, bounds))
        def connect_viewport(self, cb):
            self._cb = cb
            return Disposable(lambda: setattr(self, "_cb", None))

    seen = []
    counter = {"n": 0}

    def rasterize(_src, *, width, height, x_range, y_range):
        counter["n"] += 1
        vals = np.full((height, width), float(counter["n"]))
        return RasterResult(
            np.zeros((height, width, 4), np.uint8),
            (x_range[0], y_range[0], x_range[1], y_range[1]),
            RasterAggregate(vals, (x_range[0], y_range[0], x_range[1], y_range[1]), "count"),
        )

    target = FakeTarget()
    c = RasterController(
        source=object(), target=target, rasterize=rasterize,
        on_aggregate=seen.append, debounce_ms=10,
    )
    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    assert seen[-1].value_at(0.5, 0.5) == 1.0  # first aggregate delivered

    before = len(seen)
    c._on_done(c._build_id - 1, RasterResult(  # a superseded build
        np.zeros((4, 4, 4), np.uint8), (0, 0, 1, 1),
        RasterAggregate(np.full((4, 4), 999.0), (0, 0, 1, 1), "count")),
        None)
    assert len(seen) == before  # stale → not pushed
    c.dispose()


# ════════════════════════ Tier 2 — end-to-end hover ════════════════════════════
def _cluster(n=50_000):
    rng = np.random.default_rng(0)
    return {"x": rng.normal(size=n), "y": rng.normal(size=n)}


@pytest.mark.tier2
def test_pyqtgraph_hover_emits_value(qtbot):
    pytest.importorskip("datashader")
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    from PySide6.QtCore import QPointF

    view = qv.View(qv.Scatter(_cluster(), x="x", y="y", scale="datashader"), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.resize(500, 400)
    view.show()
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)

    events = []
    view.on(qv.HoverEvent, events.append, throttle_ms=0)

    vb = view.handle.plots[0].getViewBox()
    qtbot.waitUntil(lambda: getattr(vb, "_qtviz_rasters", None) is not None, timeout=4000)
    # move the cursor to the dense center (data ≈ (0, 0)) via a scene position
    scene_pos = vb.mapViewToScene(QPointF(0.0, 0.0))
    vb.scene().sigMouseMoved.emit(scene_pos)

    qtbot.waitUntil(lambda: bool(events), timeout=2000)
    ev = events[-1]
    assert ev.point_index is None
    assert ev.value is not None and ev.value > 0  # count under the dense center
    view.handle.dispose()  # sever the scene-mouse connection deterministically (offscreen hygiene)


@pytest.mark.tier2
def test_matplotlib_hover_emits_value(qtbot):
    pytest.importorskip("datashader")
    pytest.importorskip("matplotlib")
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib backend not registered")
    from matplotlib.backend_bases import MouseEvent

    view = qv.View(qv.Scatter(_cluster(), x="x", y="y", scale="datashader"), backend="matplotlib")
    qtbot.addWidget(view)
    view.resize(500, 400)
    view.show()
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)

    events = []
    view.on(qv.HoverEvent, events.append, throttle_ms=0)

    ax = view.handle.axes[0]
    qtbot.waitUntil(lambda: getattr(ax, "_qtviz_rasters", None) is not None, timeout=4000)
    px, py = ax.transData.transform((0.0, 0.0))  # dense center → device px
    canvas = ax.figure.canvas
    move = MouseEvent("motion_notify_event", canvas, px, py)
    canvas.callbacks.process("motion_notify_event", move)

    qtbot.waitUntil(lambda: bool(events), timeout=2000)
    ev = events[-1]
    assert ev.point_index is None
    assert ev.value is not None and ev.value > 0
    view.handle.dispose()  # sever the canvas motion connection (offscreen hygiene)
