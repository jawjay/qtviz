"""[D128] streaming through lowering — the tail rides the [D77] fast path.

`set_element_data` on pyqtgraph now handles lowered elements: relower with
the streamed arrays, write each mark item's geometry in place (`setData`) —
no rebuild. All-or-nothing: a mark-type/shape change (or a mark with no
updater) falls back to the existing rebuild path, explicitly, never
silently. Elements proven here: Ecdf (one step Polyline), Spread (one
Band), Stem (pair Polyline + pickable Markers, selectables refreshed).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T0 = np.arange(10.0)


def _pg_available():
    return "pyqtgraph" in {getattr(b, "name", b) for b in qv.backends.list_available()}


pytestmark = [pytest.mark.tier2,
              pytest.mark.skipif(not _pg_available(), reason="pyqtgraph unavailable")]


@pytest.mark.tier2
def test_ecdf_streams_in_place(qtbot):
    feed = qv.stream({"v": float})
    feed.append(v=_T0)
    el = qv.Ecdf(feed, value="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    item_before = view.native(el.id)
    handle_before = view.handle
    n_before = len(item_before.getData()[0])
    feed.append(v=np.arange(10.0, 20.0))
    qtbot.waitUntil(
        lambda: len(view.native(el.id).getData()[0]) > n_before, timeout=2000)
    assert view.native(el.id) is item_before        # same live item — no rebuild
    assert view.handle is handle_before
    _x, fr = view.native(el.id).getData()
    assert fr[-1] == pytest.approx(1.0)             # relowered: a true CDF, not raw rows


@pytest.mark.tier2
def test_spread_streams_in_place(qtbot):
    feed = qv.stream({"t": float, "lo": float, "hi": float})
    feed.append(t=_T0, lo=_T0 - 1.0, hi=_T0 + 1.0)
    el = qv.Spread(feed, x="t", lo="lo", hi="hi")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    fill_before = view.native(el.id)                # the FillBetweenItem
    lo_curve = fill_before.curves[0]
    feed.append(t=np.arange(10.0, 20.0), lo=np.zeros(10), hi=np.ones(10))
    qtbot.waitUntil(
        lambda: len(fill_before.curves[0].getData()[0]) == 20, timeout=2000)
    assert view.native(el.id) is fill_before        # same items, updated in place
    assert fill_before.curves[0] is lo_curve


@pytest.mark.tier2
def test_stem_streams_in_place_and_selectables_follow(qtbot):
    feed = qv.stream({"t": float, "v": float})
    feed.append(t=_T0, v=_T0 * 2.0)
    el = qv.Stem(feed, x="t", y="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    stalks, heads = view.native(el.id)              # pair Polyline + Markers
    feed.append(t=np.arange(10.0, 20.0), v=np.zeros(10))
    qtbot.waitUntil(lambda: len(heads.getData()[0]) == 20, timeout=2000)
    assert view.native(el.id)[0] is stalks          # in place, both items
    assert len(stalks.getData()[0]) == 40           # 2 points per stalk
    # the brush registry follows the new rows (selection stays truthful)
    vb = heads.getViewBox()
    entries = {eid: x for eid, x, _y in getattr(vb, "_selectables", ())}
    assert el.id in entries and len(entries[el.id]) == 20


@pytest.mark.tier2
def test_quiver_streams_in_place(qtbot):
    """Quiver lowers to exactly two NaN-separated polylines (shafts + heads)
    regardless of arrow count — so appends ride the fast path too."""
    feed = qv.stream({"x": float, "y": float, "u": float, "v": float})
    feed.append(x=_T0, y=_T0, u=np.ones(10), v=np.ones(10))
    el = qv.Quiver(feed, x="x", y="y", u="u", v="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    shafts, heads = view.native(el.id)
    n_before = len(shafts.getData()[0])
    feed.append(x=np.arange(10.0, 15.0), y=np.zeros(5),
                u=np.ones(5), v=np.ones(5))
    qtbot.waitUntil(
        lambda: len(shafts.getData()[0]) > n_before, timeout=2000)
    assert view.native(el.id)[0] is shafts          # same items — no rebuild


@pytest.mark.tier2
def test_shape_change_refuses_the_fast_path(qtbot):
    """The all-or-nothing guard: a mark-sequence mismatch makes
    `set_element_data` return False (the caller's rebuild fallback), never a
    partial write."""
    feed = qv.stream({"v": float})
    feed.append(v=_T0)
    el = qv.Ecdf(feed, value="v")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    vb = view.native(el.id).getViewBox()
    entry = vb._qtviz_lowered[el.id]
    entry.marks = ()                                # simulate a shape change
    arrays = el.data.resolve_channels(el.channels(), who="Ecdf")
    assert view.handle.set_element_data(el.id, arrays) is False
