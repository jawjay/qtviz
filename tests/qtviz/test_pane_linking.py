"""Structured axis sharing ([D146]) + cross-backend linking ([D151]).

`link_x`/`link_y` widen to `bool | "col" | "row"`; groups come from the grid
cells (spanning panes merge groups — the `subplot_mosaic` rule). Single-
backend grids link natively (pg `setXLink`, mpl `sharex`); host-composed
layouts (mixed backends, splitter/tabs, nested) link through the event loop
via the `_LinkController`, echo-guarded.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.compose import link_groups  # noqa: E402
from qtviz.errors import QtvizWarning, ValidationError  # noqa: E402

D = {"x": np.arange(10.0), "y": np.arange(10.0) ** 2}


def _s(**kw):
    return qv.Scatter(D, x="x", y="y", **kw)


def _c(**kw):
    return qv.Curve(D, x="x", y="y", **kw)


# ── link_groups (pure) ───────────────────────────────────────────────────────
@pytest.mark.tier1
def test_link_groups_modes():
    cells = [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]  # 2×2
    assert link_groups(cells, 4, False) == []
    assert link_groups(cells, 4, True) == [[0, 1, 2, 3]]
    assert sorted(link_groups(cells, 4, "col")) == [[0, 2], [1, 3]]
    assert sorted(link_groups(cells, 4, "row")) == [[0, 1], [2, 3]]
    assert link_groups(cells[:1], 1, True) == []  # nothing to link


@pytest.mark.tier1
def test_link_groups_span_merges():
    # A spans both rows in col 0: "row" merges everything through it
    cells = [(0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)]  # A, B, C
    assert link_groups(cells, 3, "row") == [[0, 1, 2]]
    assert link_groups(cells, 3, "col") == [[1, 2]]  # col 1 only; A alone in col 0


@pytest.mark.tier1
def test_link_vocabulary_validation():
    with pytest.raises(ValidationError, match="link_x must be"):
        qv.LayoutOptions(link_x="diag")
    with pytest.raises(ValidationError, match="needs a grid"):
        qv.Layout.splitter([_s(), _c()],
                           options=qv.LayoutOptions(link_x="col"))
    ok = qv.Layout.splitter([_s(), _c()], options=qv.LayoutOptions(link_x=True))
    assert ok.options.link_x is True
    assert qv.Layout([_s(), _c()]).opts(link_y="row").options.link_y == "row"


# ── single-backend grids: native group linking ───────────────────────────────
@pytest.mark.tier2
@pytest.mark.parametrize("name", ["pyqtgraph", "matplotlib"])
def test_col_linking_in_grid(name, qtbot):
    lay = qv.Layout.grid({"a": _s(), "b": _c(), "c": _c(), "d": _c()},
                         options=qv.LayoutOptions(cols=2, link_x="col"))
    view = qv.View(lay, backend=name)
    qtbot.addWidget(view)
    b_before = view.pane("b").capture().x_range
    view.pane("a").set_range(x=(3.0, 4.0))  # col 0: a (0,0) and c (1,0)
    assert view.pane("c").capture().x_range == pytest.approx((3.0, 4.0), rel=1e-3)
    assert view.pane("b").capture().x_range == pytest.approx(b_before, rel=1e-3)


@pytest.mark.tier2
def test_span_merges_row_groups_in_render(qtbot):
    """The spanning pane merges both row groups → every pane links to it.
    Asserted on the native linkage (pg maps linked ranges pixel-proportionally,
    so range equality needs real geometry — unavailable offscreen)."""
    import pyqtgraph as pg

    lay = qv.Layout.mosaic([["left", "right_top"], ["left", "right_bot"]],
                           left=_s(), right_top=_c(), right_bot=_c(),
                           options=qv.LayoutOptions(link_y="row"))
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    left_vb = view.pane("left").native.getViewBox()
    for label in ("right_top", "right_bot"):
        vb = view.pane(label).native.getViewBox()
        assert vb.linkedView(pg.ViewBox.YAxis) is left_vb


# ── host-composed layouts: [D151] event-loop linking ─────────────────────────
@pytest.mark.tier2
def test_splitter_links_all_panes(qtbot):
    lay = qv.Layout.splitter({"left": _s(), "right": _c()},
                             options=qv.LayoutOptions(link_x=True))
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.pane("left").set_range(x=(2.0, 7.0))
    view.handle.event_bus._drain()
    assert view.pane("right").capture().x_range == pytest.approx(
        (2.0, 7.0), rel=1e-3)


@pytest.mark.tier2
def test_mixed_backend_linking(qtbot):
    pytest.importorskip("matplotlib")
    lay = qv.Layout.grid({"pg": _s(backend_hint="pyqtgraph"),
                          "mpl": _c(backend_hint="matplotlib")},
                         options=qv.LayoutOptions(link_x=True))
    with warnings.catch_warnings():
        warnings.simplefilter("error", QtvizWarning)  # host honors link now
        view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.pane("pg").set_range(x=(1.0, 6.0))
    view.handle.event_bus._drain()
    assert view.pane("mpl").capture().x_range == pytest.approx(
        (1.0, 6.0), rel=1e-3)
    # …and back: zoom the mpl pane, the pg pane follows
    view.pane("mpl").set_range(x=(0.0, 3.0))
    view.handle.event_bus._drain()
    assert view.pane("pg").capture().x_range == pytest.approx(
        (0.0, 3.0), rel=1e-3)


@pytest.mark.tier2
def test_mixed_col_linking(qtbot):
    pytest.importorskip("matplotlib")
    lay = qv.Layout.grid({"a": _s(backend_hint="pyqtgraph"),
                          "b": _c(backend_hint="matplotlib"),
                          "c": _c(backend_hint="pyqtgraph"),
                          "d": _c(backend_hint="matplotlib")},
                         options=qv.LayoutOptions(cols=2, link_x="col"))
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    b_before = view.pane("b").capture().x_range
    view.pane("a").set_range(x=(4.0, 5.0))  # col 0 = a, c (pg + pg via host)
    view.handle.event_bus._drain()
    assert view.pane("c").capture().x_range == pytest.approx((4.0, 5.0), rel=1e-3)
    assert view.pane("b").capture().x_range == pytest.approx(b_before, rel=1e-3)


@pytest.mark.tier2
def test_nested_pane_excluded_with_warning(qtbot):
    inner = qv.Layout.grid({"i1": _s(), "i2": _c()})
    lay = qv.Layout([inner, _s(), _c()],
                    options=qv.LayoutOptions(link_x=True))
    with pytest.warns(QtvizWarning, match="nested Layout pane is excluded"):
        view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    i1_before = view.pane("i1").capture().x_range
    view.pane("2").set_range(x=(2.0, 8.0))  # the two flat outer panes link
    view.handle.event_bus._drain()
    assert view.pane("3").capture().x_range == pytest.approx((2.0, 8.0), rel=1e-3)
    assert view.pane("i1").capture().x_range == pytest.approx(i1_before, rel=1e-3)


@pytest.mark.tier2
def test_linking_converges_no_feedback_loop(qtbot):
    lay = qv.Layout.splitter({"left": _s(), "right": _c()},
                             options=qv.LayoutOptions(link_x=True, link_y=True))
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    for i in range(5):  # repeated zooms terminate and stay consistent
        view.pane("left").set_range(x=(float(i), float(i) + 1.0))
        view.handle.event_bus._drain()
    assert view.pane("right").capture().x_range == pytest.approx(
        (4.0, 5.0), rel=1e-3)
