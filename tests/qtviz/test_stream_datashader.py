"""Roadmap wave 2, increment 4 — streaming × datashader (the capability-track
interleave; retrospective §4.2).

A `scale="datashader"` element over a `qv.stream` used to fall off the [D77]
ladder to a full rebuild every tick. Now the element's `RasterController`
(which reads the *live* source at every aggregation) exposes `refresh()`, and
`set_element_data` routes datashaded elements to it: the current viewport
re-aggregates off-thread — debounced, stale-dropped — with no rebuild.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("datashader")


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


def _controller_for(handle, element_id, plots=True):
    holders = ([p.getViewBox() for p in handle.plots] if plots
               else [s["ax"] for s in handle._surfaces])
    for h in holders:
        for c in getattr(h, "_qtviz_rasters", ()):
            if getattr(c, "element_id", None) == element_id:
                return c
    return None


@pytest.mark.tier2
def test_pg_streamed_raster_refreshes_in_place(qtbot):
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=np.linspace(0, 10, 5000), v=np.random.default_rng(0).normal(0, 1, 5000))
    el = qv.Scatter(feed, x="t", y="v", scale="datashader")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    controller = _controller_for(handle, el.id)
    assert controller is not None
    item_before = handle.native(el.id)
    builds_before = controller._build_id
    ok = handle.set_element_data(el.id, {"t": np.array([1.0]), "v": np.array([1.0])})
    assert ok is True                                   # rung 1, not a rebuild
    assert handle.native(el.id) is item_before          # same live raster item
    qtbot.waitUntil(lambda: controller._build_id > builds_before, timeout=3000)


@pytest.mark.tier2
def test_mpl_streamed_raster_refreshes_in_place(qtbot):
    pytest.importorskip("matplotlib")
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=np.linspace(0, 10, 5000), v=np.random.default_rng(1).normal(0, 1, 5000))
    el = qv.Scatter(feed, x="t", y="v", scale="datashader")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    controller = _controller_for(handle, el.id, plots=False)
    assert controller is not None
    builds_before = controller._build_id
    assert handle.set_element_data(el.id, {"t": np.array([1.0]),
                                           "v": np.array([1.0])}) is True
    qtbot.waitUntil(lambda: controller._build_id > builds_before, timeout=3000)


@pytest.mark.tier2
def test_view_binding_routes_stream_appends_to_the_controller(qtbot):
    """End to end through the View's _StreamBinding: an append re-aggregates
    the live source (the new rows appear in the raster) without replacing the
    native item."""
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=np.zeros(2000), v=np.zeros(2000))     # a tight blob at (0, 0)
    el = qv.Scatter(feed, x="t", y="v", scale="datashader")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    handle = view.handle
    item_before = view.native(el.id)
    controller = _controller_for(handle, el.id)
    builds_before = controller._build_id
    feed.append(t=np.full(500, 0.1), v=np.full(500, 0.1))
    qtbot.waitUntil(lambda: controller._build_id > builds_before, timeout=5000)
    assert view.native(el.id) is item_before            # in place — no rebuild
    assert view.handle is handle
