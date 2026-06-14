"""Tier-2 — matplotlib interaction (milestone M6).

matplotlib is the static + slow-interactive backend: range (axes lim
callbacks), pick (PathCollection picker), and programmatic brush. Events are
driven by setting limits / processing a synthetic pick event / calling
select_bounds; throttled deliveries flushed via the bus `_drain()` hook.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("matplotlib")

pytestmark = pytest.mark.tier2


@pytest.fixture
def mplview(qtbot):
    import qtviz.backends as B

    if "matplotlib" not in B.list_available():
        pytest.skip("matplotlib backend not registered")

    def make(root):
        view = qv.View(root, backend="matplotlib")
        qtbot.addWidget(view)
        return view

    return make


def test_range_event_fires_on_zoom(mplview, table):
    view = mplview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.RangeEvent, got.append)
    view.handle.axes[0].set_xlim(2, 8)
    view.handle.event_bus._drain()
    assert got and got[-1].x[0] == pytest.approx(2, abs=0.1)


def test_pick_event_on_point(mplview, table):
    from matplotlib.backend_bases import MouseEvent, PickEvent

    view = mplview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.PickEvent, got.append)
    ax = view.handle.axes[0]
    canvas = view.handle.widget
    artist = ax.collections[0]
    me = MouseEvent("button_press_event", canvas, 10, 10)
    canvas.callbacks.process("pick_event", PickEvent("pick_event", canvas, me, artist, ind=[3]))
    assert got and got[0].point_index == 3


def test_select_event_via_brush(mplview, table):
    view = mplview(qv.Scatter(table, x="x", y="y"))
    got = []
    view.on(qv.SelectEvent, got.append)
    view.handle.select_bounds(0, 2.0, -1e9, 5.0, 1e9)
    view.handle.event_bus._drain()
    assert got and got[0].bounds == (2.0, -1e9, 5.0, 1e9)
    assert got[0].indices and all(2.0 <= table["x"][i] <= 5.0 for i in got[0].indices)


def test_linked_axes_share_range(mplview, table):
    layout = qv.Layout(
        [qv.Scatter(table, x="x", y="y"), qv.Curve(table, x="x", y="y")],
        options=qv.LayoutOptions(link_x=True),
    )
    view = mplview(layout)
    a0, a1 = view.handle.axes
    a0.set_xlim(3, 7)
    assert a1.get_xlim()[0] == pytest.approx(3, abs=0.1)
