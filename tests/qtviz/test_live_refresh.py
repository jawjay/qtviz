"""0.6 increment 2 — incremental refresh ([D77], resolves [D7]).

A view on a `qv.stream` updates when the producer appends: pyqtgraph writes
the live items **in place** (`set_element_data` — no rebuild, `streaming=True`
finally backed by code); appends coalesce to one refresh per tick; backends
without the fast path fall back honestly (mpl: debounced rebuild).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T0 = np.arange(10.0)


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


def _fed(window=None):
    feed = qv.stream({"t": float, "v": float}, window=window)
    feed.append(t=_T0, v=_T0 * 2.0)
    return feed


@pytest.mark.tier2
def test_pyqtgraph_stream_updates_in_place(qtbot):
    feed = _fed()
    el = qv.Curve(feed, x="t", y="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    item_before = view.native(el.id)
    handle_before = view.handle
    feed.append(t=np.arange(10.0, 20.0), v=np.arange(10.0, 20.0) * 2.0)
    qtbot.waitUntil(lambda: len(view.native(el.id).getData()[0]) == 20, timeout=2000)
    assert view.native(el.id) is item_before            # same live item — no rebuild
    assert view.handle is handle_before
    x, y = view.native(el.id).getData()
    assert np.allclose(y, x * 2.0)


@pytest.mark.tier2
def test_appends_coalesce_to_one_refresh_per_tick(qtbot, monkeypatch):
    feed = _fed()
    el = qv.Scatter(feed, x="t", y="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    calls: list = []
    original = type(view.handle).set_element_data

    def counting(self, element_id, arrays):
        calls.append(element_id)
        return original(self, element_id, arrays)

    monkeypatch.setattr(type(view.handle), "set_element_data", counting)
    for i in range(50):                                 # a burst, no event loop between
        feed.append(t=float(100 + i), v=float(i))
    qtbot.waitUntil(lambda: bool(calls), timeout=2000)
    qtbot.wait(50)                                      # let any stragglers fire
    assert len(calls) <= 2                              # coalesced ([D7]) — not 50
    assert len(view.native(el.id).getData()[0]) == 60   # …and nothing was lost


@pytest.mark.tier2
def test_rolling_window_rolls_the_rendered_item(qtbot):
    feed = _fed(window=15)
    el = qv.Curve(feed, x="t", y="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    feed.append(t=np.arange(10.0, 20.0), v=np.zeros(10))    # 20 rows → keep last 15
    qtbot.waitUntil(lambda: len(view.native(el.id).getData()[0]) == 15, timeout=2000)
    x, _y = view.native(el.id).getData()
    assert x[0] == 5.0                                  # oldest rows rolled out


@pytest.mark.tier2
def test_refresh_respects_a_user_zoom(qtbot):
    feed = _fed()
    el = qv.Curve(feed, x="t", y="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    vb = view.handle.plots[0].getViewBox()
    vb.setXRange(2.0, 4.0, padding=0)                   # user zoom
    feed.append(t=np.arange(10.0, 500.0), v=np.zeros(490))
    qtbot.waitUntil(lambda: len(view.native(el.id).getData()[0]) == 500, timeout=2000)
    (x0, x1), _ = vb.viewRange()
    assert np.allclose((x0, x1), (2.0, 4.0))            # never re-ranged under the user


@pytest.mark.tier2
def test_brush_selectables_stay_truthful_after_appends(qtbot):
    feed = _fed()
    el = qv.Scatter(feed, x="t", y="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    feed.append(t=100.0, v=200.0)                       # the new point
    qtbot.waitUntil(lambda: len(view.native(el.id).getData()[0]) == 11, timeout=2000)
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0)
    view.handle.plots[0].getViewBox().select_bounds(99.0, 199.0, 101.0, 201.0)
    assert got and got[-1].indices == [10]              # streamed row is selectable


@pytest.mark.tier2
def test_streamed_color_by_falls_back_and_stays_correct(qtbot):
    """Per-point styling can't be poked through setData — the binding falls back
    to a full handle.update, and the render is still right."""
    feed = qv.stream({"t": float, "v": float, "c": float})
    feed.append(t=_T0, v=_T0, c=_T0)
    el = qv.Scatter(feed, x="t", y="v", color_by="c")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    feed.append(t=99.0, v=99.0, c=99.0)
    qtbot.waitUntil(lambda: len(view.native(el.id).getData()[0]) == 11, timeout=2000)


@pytest.mark.tier2
def test_matplotlib_falls_back_to_debounced_rebuild(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    feed = _fed()
    el = qv.Curve(feed, x="t", y="v")
    view = qv.View(el, backend="matplotlib")
    qtbot.addWidget(view)
    feed.append(t=np.arange(10.0, 20.0), v=np.zeros(10))

    def updated():
        artist = view.native(el.id)
        return artist is not None and len(artist.get_xdata()) == 20

    qtbot.waitUntil(updated, timeout=3000)              # honest fallback: rebuilt


@pytest.mark.tier2
def test_stream_under_log_axis_stays_r1_consistent(qtbot):
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=np.array([1.0, 10.0]), v=np.array([1.0, 2.0]))
    node = qv.Overlay([qv.Curve(feed, x="t", y="v")],
                      options=qv.OverlayOptions(x=qv.AxisSpec(scale="log")))
    el = node.children[0]
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    feed.append(t=100.0, v=3.0)
    qtbot.waitUntil(lambda: len(view.native(el.id).getData()[0]) == 3, timeout=2000)
    x, _y = view.native(el.id).getData()
    assert np.allclose(x, [0.0, 1.0, 2.0])              # exponent space internally
