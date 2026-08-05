"""The public pane surface ([D147], design/pane-handles.md S3).

`view.pane(...)` / `view.panes` — the "Axes of qtviz": interaction-side verbs
(set_range / autorange / select / capture / native / elements) on a live
facade that goes dead with its render (fetch fresh, never cache).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.errors import DisposedError  # noqa: E402

pytestmark = pytest.mark.tier2

D = {"x": np.arange(10.0), "y": np.arange(10.0) ** 2}
BACKENDS = ["pyqtgraph", "matplotlib"]


def _grid():
    return qv.Layout.grid({"price": qv.Scatter(D, x="x", y="y"),
                           "volume": qv.Curve(D, x="x", y="y")})


@pytest.mark.parametrize("name", BACKENDS)
def test_view_pane_surface(name, qtbot):
    view = qv.View(_grid(), backend=name)
    qtbot.addWidget(view)
    assert [p.label for p in view.panes] == ["price", "volume"]
    pane = view.pane("price")
    pane.set_range(x=(2.0, 6.0))
    assert pane.capture().x_range == pytest.approx((2.0, 6.0), rel=1e-3)
    assert view.pane(0).label == "price"
    assert pane.native is not None
    assert len(pane.elements) == 1
    assert view.root["price"] is not None  # root property pairs with with_pane


@pytest.mark.parametrize("name", BACKENDS)
def test_autorange_resets_a_zoom(name, qtbot):
    view = qv.View(_grid(), backend=name)
    qtbot.addWidget(view)
    pane = view.pane("price")
    pane.set_range(x=(1000.0, 2000.0))  # far off the data
    pane.autorange()
    lo, hi = pane.capture().x_range
    assert lo <= 1.0 and hi >= 8.0  # the data (0..9) is back in view


@pytest.mark.parametrize("name", BACKENDS)
def test_select_emits_pane_scoped_select_events(name, qtbot):
    scatter = qv.Scatter(D, x="x", y="y")
    view = qv.View(qv.Layout.grid({"a": scatter, "b": qv.Curve(D, x="x", y="y")}),
                   backend=name)
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.SelectEvent, got.append)
    view.pane("a").select(1.5, 0.0, 4.5, 100.0)  # x in (1.5, 4.5) → rows 2..4
    assert [e.source_id for e in got] == [scatter.id]  # pane "a" only
    assert got[0].indices == [2, 3, 4]


@pytest.mark.parametrize("name", BACKENDS)
def test_stale_pane_goes_dead_after_rebuild(name, qtbot):
    view = qv.View(_grid(), backend=name)
    qtbot.addWidget(view)
    stale = view.pane("price")
    view.set_theme(qv.Theme.dark())  # rebuild disposes the old render
    assert not stale.alive
    with pytest.raises(DisposedError, match="disposed render"):
        stale.set_range(x=(0.0, 1.0))
    with pytest.raises(DisposedError):
        stale.capture()
    fresh = view.pane("price")
    assert fresh.alive
    fresh.set_range(x=(0.0, 1.0))  # the fresh facade works


def test_single_surface_pane_no_key(qtbot):
    view = qv.View(qv.Scatter(D, x="x", y="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.pane().set_range(y=(0.0, 50.0))
    assert view.pane().capture().y_range == pytest.approx((0.0, 50.0), rel=1e-3)


def test_composite_view_pane_by_label(qtbot):
    lay = qv.Layout.splitter({"left": qv.Scatter(D, x="x", y="y"),
                              "right": qv.Curve(D, x="x", y="y")})
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.pane("right").set_range(x=(3.0, 5.0))
    assert view.handle.capture_state().get("right").x_range == pytest.approx(
        (3.0, 5.0), rel=1e-3)
