"""Pane protocol + whole-render state ([D147]/[D150], design/pane-handles.md S1).

The regression that matters most: multi-pane view state used to be pane-0-only
(every backend) or absent (composite) — a silent [D2] violation. These tests
pin the all-pane contract: capture covers every pane, restore matches by
label, and state survives rebuilds, backend switches, and the composite host.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.backend import CompositeRenderHandle, LayoutState, ViewState  # noqa: E402

pytestmark = pytest.mark.tier2

D = {"x": np.arange(10.0), "y": np.arange(10.0) ** 2}
BACKENDS = ["pyqtgraph", "matplotlib"]


def _two_pane():
    return qv.Scatter(D, x="x", y="y") + qv.Curve(D, x="x", y="y")


# ── LayoutState value semantics (pure, no Qt) ────────────────────────────────
@pytest.mark.tier1
def test_layout_state_value_semantics():
    empty = LayoutState()
    assert empty.get("0") is None
    assert empty.first == ViewState()
    assert empty.x_range is None
    vs = ViewState(x_range=(1.0, 2.0), y2_range=(3.0, 4.0))
    st = LayoutState((("a", vs), ("b", ViewState())))
    assert st.get("a") is vs and st.get("missing") is None
    # single-surface conveniences read the FIRST pane
    assert st.x_range == (1.0, 2.0) and st.y2_range == (3.0, 4.0)


# ── all-pane capture / label-matched restore ─────────────────────────────────
@pytest.mark.parametrize("name", BACKENDS)
def test_capture_covers_every_pane(name, qtbot):
    view = qv.View(_two_pane(), backend=name)
    qtbot.addWidget(view)
    view.handle.panes()[1].set_range(x=(100.0, 200.0))
    st = view.handle.capture_state()
    assert [lb for lb, _ in st.panes] == ["0", "1"]
    assert st.get("1").x_range == pytest.approx((100.0, 200.0), rel=1e-3)
    assert st.get("0").x_range != pytest.approx((100.0, 200.0), rel=1e-3)


@pytest.mark.parametrize("name", BACKENDS)
def test_state_survives_rebuild(name, qtbot):
    view = qv.View(_two_pane(), backend=name)
    qtbot.addWidget(view)
    view.handle.panes()[1].set_range(x=(100.0, 200.0))
    view.set_theme(qv.Theme.dark())  # full rebuild
    st = view.handle.capture_state()
    assert st.get("1").x_range == pytest.approx((100.0, 200.0), rel=1e-3)


def test_state_survives_backend_switch(qtbot):
    view = qv.View(_two_pane(), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.handle.panes()[1].set_range(x=(100.0, 200.0), y=(7.0, 9.0))
    view.set_backend("matplotlib")
    ax1 = view.handle.axes[1]
    assert tuple(ax1.get_xlim()) == pytest.approx((100.0, 200.0), rel=1e-3)
    assert tuple(ax1.get_ylim()) == pytest.approx((7.0, 9.0), rel=1e-3)


def test_restore_drops_unknown_labels(qtbot):
    view = qv.View(_two_pane(), backend="pyqtgraph")
    qtbot.addWidget(view)
    stale = LayoutState((("7", ViewState(x_range=(1.0, 2.0))),))
    view.handle.restore_state(stale)  # no raise; nothing to match ([D150])


def test_viewstate_shorthand_targets_first_pane(qtbot):
    view = qv.View(_two_pane(), backend="pyqtgraph")
    qtbot.addWidget(view)
    before = view.handle.capture_state().get("1").x_range
    view.handle.restore_state(ViewState(x_range=(5.0, 9.0)))
    st = view.handle.capture_state()
    assert st.get("0").x_range == pytest.approx((5.0, 9.0), rel=1e-3)
    assert st.get("1").x_range == pytest.approx(before, rel=1e-3)


# ── pane lookup + metadata ───────────────────────────────────────────────────
@pytest.mark.parametrize("name", BACKENDS)
def test_pane_lookup_and_metadata(name, qtbot):
    scatter = qv.Scatter(D, x="x", y="y")
    view = qv.View(scatter + qv.Curve(D, x="x", y="y"), backend=name)
    qtbot.addWidget(view)
    h = view.handle
    assert h.pane("1").label == "1"
    assert h.pane(1).label == "1"
    with pytest.raises(qv.errors.ValidationError):
        h.pane()  # ambiguous on a multi-pane render
    with pytest.raises(KeyError):
        h.pane("price")
    assert h.pane("0").native is not None
    assert h.pane("0").elements == (scatter.id,)


def test_single_surface_is_one_pane(qtbot):
    view = qv.View(qv.Scatter(D, x="x", y="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle.pane().label == "0"  # no key needed


# ── composite (mixed / splitter / nested) ────────────────────────────────────
def test_composite_panes_flatten_and_capture(qtbot):
    lay = qv.Layout.splitter([_two_pane(), qv.Curve(D, x="x", y="y")])
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    h = view.handle
    assert isinstance(h, CompositeRenderHandle)
    assert [p.label for p in h.panes()] == ["0", "1", "2"]
    h.pane("2").set_range(x=(50.0, 60.0))
    st = h.capture_state()
    assert st.get("2").x_range == pytest.approx((50.0, 60.0), rel=1e-3)
    h.restore_state(st)  # label-matched round-trip, no raise


def test_composite_state_survives_rebuild(qtbot):
    lay = qv.Layout.splitter([_two_pane(), qv.Curve(D, x="x", y="y")])
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.handle.pane("2").set_range(x=(50.0, 60.0))
    view.set_theme(qv.Theme.dark())
    st = view.handle.capture_state()
    assert st.get("2").x_range == pytest.approx((50.0, 60.0), rel=1e-3)


# ── named panes end-to-end ([D145] × [D150]) ─────────────────────────────────
@pytest.mark.parametrize("name", BACKENDS)
def test_given_labels_key_the_panes(name, qtbot):
    lay = qv.Layout.grid({"price": qv.Scatter(D, x="x", y="y"),
                          "volume": qv.Curve(D, x="x", y="y")})
    view = qv.View(lay, backend=name)
    qtbot.addWidget(view)
    h = view.handle
    assert [p.label for p in h.panes()] == ["price", "volume"]
    h.pane("volume").set_range(x=(100.0, 200.0))
    assert h.capture_state().get("volume").x_range == pytest.approx(
        (100.0, 200.0), rel=1e-3)


def test_labeled_state_survives_backend_switch(qtbot):
    lay = qv.Layout.grid({"price": qv.Scatter(D, x="x", y="y"),
                          "volume": qv.Curve(D, x="x", y="y")})
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.handle.pane("volume").set_range(x=(100.0, 200.0))
    view.set_backend("matplotlib")
    assert view.handle.capture_state().get("volume").x_range == pytest.approx(
        (100.0, 200.0), rel=1e-3)


def test_mosaic_labels_key_composite_panes(qtbot):
    lay = qv.Layout.mosaic([["price", "book"], ["volume", "book"]],
                           price=qv.Scatter(D, x="x", y="y"),
                           book=qv.Curve(D, x="x", y="y"),
                           volume=qv.Curve(D, x="x", y="y"))
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    assert [p.label for p in view.handle.panes()] == ["price", "book", "volume"]
    # a mosaic pane spans its rectangle in the rendered grid too
    view.handle.pane("book").set_range(y=(0.0, 5.0))
    assert view.handle.capture_state().get("book").y_range == pytest.approx(
        (0.0, 5.0), rel=1e-3)


def test_labels_survive_root_swap_with_pane(qtbot):
    lay = qv.Layout.grid({"price": qv.Scatter(D, x="x", y="y"),
                          "volume": qv.Curve(D, x="x", y="y")})
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.handle.pane("price").set_range(x=(3.0, 4.0))
    view.set_root(lay.with_pane("volume", qv.Scatter(D, x="x", y="y")))
    # untouched pane keeps its zoom across the declarative pane swap
    assert view.handle.capture_state().get("price").x_range == pytest.approx(
        (3.0, 4.0), rel=1e-3)


@pytest.mark.parametrize("name", BACKENDS)
def test_nested_grid_renders(name, qtbot):
    """Regression: a nested homogeneous grid crashed in the backend cell
    renderer (`Layout` has no `.lower`) — it now routes to the LayoutHost."""
    inner = qv.Scatter(D, x="x", y="y") + qv.Curve(D, x="x", y="y")
    view = qv.View(qv.Layout([inner, qv.Curve(D, x="x", y="y")]), backend=name)
    qtbot.addWidget(view)
    assert isinstance(view.handle, CompositeRenderHandle)
    assert [p.label for p in view.handle.panes()] == ["0", "1", "2"]
