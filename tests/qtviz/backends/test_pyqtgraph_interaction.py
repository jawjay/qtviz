"""Tier-2 — pyqtgraph interaction (milestone M4).

Native pyqtgraph signals → typed qtviz events through the EventBus, plus
linked axes. Events are driven by emitting the native signal / calling the
programmatic brush directly (deterministic, no synthetic OS mouse events);
throttled deliveries are flushed via the bus `_drain()` test hook.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")
pg = pytest.importorskip("pyqtgraph")

pytestmark = pytest.mark.tier2


@pytest.fixture
def pgview(qtbot):
    import qtviz.backends as B

    if "pyqtgraph" not in B.list_available():
        pytest.skip("pyqtgraph backend not registered")

    def make(root):
        view = qv.View(root, backend="pyqtgraph")
        qtbot.addWidget(view)
        return view

    return make


def _scatter_item(plot):
    return next(it for it in plot.listDataItems() if isinstance(it, pg.ScatterPlotItem))


def test_range_event_fires_on_zoom(pgview, table):
    view = pgview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.RangeEvent, got.append)
    view.handle.plots[0].setXRange(2, 8, padding=0)
    view.handle.event_bus._drain()  # RangeEvent is throttled; flush deterministically
    assert got and isinstance(got[-1], qv.RangeEvent)
    assert got[-1].x[0] == pytest.approx(2, abs=0.1) and got[-1].x[1] == pytest.approx(8, abs=0.1)


def test_pick_event_on_point_click(pgview, table):
    view = pgview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.PickEvent, got.append)
    sp = _scatter_item(view.handle.plots[0])
    sp.sigClicked.emit(sp, [sp.points()[3]], None)
    assert got and got[0].point_index == 3


def test_hover_event_on_and_off(pgview, table):
    view = pgview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.HoverEvent, got.append)
    sp = _scatter_item(view.handle.plots[0])
    sp.sigHovered.emit(sp, [sp.points()[5]], None)
    sp.sigHovered.emit(sp, [], None)
    view.handle.event_bus._drain()  # flush the coalesced trailing hover
    assert got[0].point_index == 5
    assert got[-1].point_index is None


def test_select_event_via_brush(pgview, table):
    view = pgview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.SelectEvent, got.append)
    view.handle.plots[0].getViewBox().select_bounds(2.0, -1e9, 5.0, 1e9)
    view.handle.event_bus._drain()  # SelectEvent is throttled
    assert got and got[0].bounds == (2.0, -1e9, 5.0, 1e9)
    # x is linspace(0,10,N); [2,5] selects a contiguous, non-empty index range.
    assert got[0].indices and all(2.0 <= table["x"][i] <= 5.0 for i in got[0].indices)


def test_linked_axes_share_range(pgview, table):
    layout = qv.Layout(
        [qv.Scatter(table, x="x", y="y"), qv.Curve(table, x="x", y="y")],
        options=qv.LayoutOptions(link_x=True),
    )
    view = pgview(layout)
    p0, p1 = view.handle.plots
    p0.setXRange(3, 7, padding=0)
    (x0, x1), _ = p1.getViewBox().viewRange()
    assert x0 == pytest.approx(3, abs=0.6) and x1 == pytest.approx(7, abs=0.6)


def test_unlinked_axes_are_independent(pgview, table):
    layout = qv.Layout([qv.Scatter(table, x="x", y="y"), qv.Curve(table, x="x", y="y")])
    view = pgview(layout)
    p0, p1 = view.handle.plots
    before = p1.getViewBox().viewRange()[0]
    p0.setXRange(3, 4, padding=0)
    assert p1.getViewBox().viewRange()[0] == pytest.approx(before, abs=0.01)
