"""Pane identity on events ([D149], design/pane-handles.md S4).

Every event carries `pane` — the label of the surface it came from; surface
events (range/tap) carry the label as `source_id` too (replacing the old
per-render random uuid). `view.on(pane=…)` scopes a subscription to one pane,
composing with `source=`; the composite host's label shim maps hosted
children's local labels to the layout's flat ones.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier2

D = {"x": np.arange(10.0), "y": np.arange(10.0) ** 2}
BACKENDS = ["pyqtgraph", "matplotlib"]


def _grid():
    return qv.Layout.grid({"price": qv.Scatter(D, x="x", y="y"),
                           "volume": qv.Curve(D, x="x", y="y")})


@pytest.mark.parametrize("name", BACKENDS)
def test_range_event_carries_pane_label(name, qtbot):
    view = qv.View(_grid(), backend=name)
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.RangeEvent, got.append, throttle_ms=0)
    view.pane("volume").set_range(x=(2.0, 5.0))
    assert got, "no RangeEvent emitted"
    ev = got[-1]
    assert ev.pane == "volume"
    assert ev.source_id == "volume"  # surface events: the label IS the source


@pytest.mark.parametrize("name", BACKENDS)
def test_select_event_carries_pane_and_element(name, qtbot):
    scatter = qv.Scatter(D, x="x", y="y")
    view = qv.View(qv.Layout.grid({"a": scatter, "b": qv.Curve(D, x="x", y="y")}),
                   backend=name)
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.SelectEvent, got.append)
    view.pane("a").select(1.5, 0.0, 4.5, 100.0)
    assert [e.pane for e in got] == ["a"]
    assert got[0].source_id == scatter.id  # element events keep the element id


@pytest.mark.parametrize("name", BACKENDS)
def test_on_pane_filter(name, qtbot):
    view = qv.View(_grid(), backend=name)
    qtbot.addWidget(view)
    price_events: list = []
    view.on(qv.RangeEvent, price_events.append, throttle_ms=0, pane="price")
    view.pane("volume").set_range(x=(2.0, 5.0))  # filtered out
    view.pane("price").set_range(x=(1.0, 3.0))
    assert price_events and all(e.pane == "price" for e in price_events)


def test_on_pane_composes_with_source(qtbot):
    s1, s2 = qv.Scatter(D, x="x", y="y"), qv.Scatter(D, x="x", y="y")
    view = qv.View((s1 * s2) + qv.Curve(D, x="x", y="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0, pane="0", source=s2)
    view.pane("0").select(-1.0, -1.0, 100.0, 100.0)  # emits for s1 AND s2
    assert [e.source_id for e in got] == [s2.id]


def test_composite_shim_maps_local_to_flat_labels(qtbot):
    """A hosted child stamps its LOCAL labels; the composite shim rewrites
    them to the layout's flat ones on delivery — splitter panes report as
    'left'/'right', not each child's own '0'."""
    lay = qv.Layout.splitter({"left": qv.Scatter(D, x="x", y="y"),
                              "right": qv.Curve(D, x="x", y="y")})
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.RangeEvent, got.append, throttle_ms=0)
    view.pane("right").set_range(x=(2.0, 5.0))
    assert any(e.pane == "right" and e.source_id == "right" for e in got)
    assert not any(e.pane == "0" and e.x == (2.0, 5.0) for e in got)


def test_nested_grid_events_carry_flat_labels(qtbot):
    inner = qv.Layout.grid({"a": qv.Scatter(D, x="x", y="y"),
                            "b": qv.Curve(D, x="x", y="y")})
    view = qv.View(qv.Layout([inner, qv.Curve(D, x="x", y="y")]),
                   backend="pyqtgraph")
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.RangeEvent, got.append, throttle_ms=0)
    view.pane("b").set_range(x=(1.0, 2.0))
    view.pane("2").set_range(x=(3.0, 4.0))  # the unlabeled outer pane
    panes = [e.pane for e in got]
    assert "b" in panes and "2" in panes
