"""Inset axes ([D152]–[D154], design/inset-axes.md).

I1 (tier-1): the node, validation, pipeline recursion, negotiation.
I2–I4 (tier-2): rendering, pane integration, and the static indicator live
in the sections below as those steps land.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.compose import _elements_of  # noqa: E402
from qtviz.data import node_is_lazy, resolve_node  # noqa: E402
from qtviz.errors import ValidationError  # noqa: E402

D = {"x": np.arange(10.0), "y": np.arange(10.0) ** 2}


def _s(**kw):
    return qv.Scatter(D, x="x", y="y", **kw)


def _zoom():
    return qv.Curve(D, x="x", y="y").opts(x=qv.AxisSpec(lim=(2.0, 4.0)),
                                          y=qv.AxisSpec(lim=(4.0, 16.0)))


# ── I1: the node ─────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_inset_validation():
    ok = qv.Inset(_zoom(), rect=(0.5, 0.5, 0.4, 0.4), label="zoom")
    assert ok.rect == (0.5, 0.5, 0.4, 0.4) and ok.label == "zoom"
    with pytest.raises(ValidationError, match="Element or Overlay"):
        qv.Inset(qv.Layout([_s()]), rect=(0, 0, 0.5, 0.5))
    with pytest.raises(ValidationError, match="Element or Overlay"):
        qv.Inset("not a node", rect=(0, 0, 0.5, 0.5))
    with pytest.raises(ValidationError, match="depth 1"):
        qv.Inset(_s() * qv.Inset(_s(), rect=(0, 0, 0.3, 0.3)),
                 rect=(0, 0, 0.5, 0.5))
    with pytest.raises(ValidationError, match="width/height"):
        qv.Inset(_s(), rect=(0.1, 0.1, 0.0, 0.5))
    with pytest.raises(ValidationError, match="sane"):
        qv.Inset(_s(), rect=(3.0, 0.1, 0.5, 0.5))
    with pytest.raises(ValidationError, match="non-empty"):
        qv.Inset(_s(), rect=(0, 0, 0.5, 0.5), label="")


@pytest.mark.tier1
def test_inset_value_identity():
    child = _s()
    a = qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="z")
    assert a == qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="z")
    assert a != qv.Inset(child, rect=(0.1, 0.5, 0.4, 0.4), label="z")
    assert a != qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="w")
    assert a != qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="z",
                         indicate=True)


@pytest.mark.tier1
def test_resolve_recurses_into_child():
    inset = qv.Inset(_s(), rect=(0.5, 0.5, 0.4, 0.4))
    node = _s() * inset
    resolved = resolve_node(node)
    inner = [el for el in _elements_of(resolved) if isinstance(el, qv.Scatter)]
    assert len(inner) == 2
    for el in inner:  # both the parent scatter AND the inset's resolved
        assert el.data.resolve_channels(el.channels())["x"].shape == (10,)


@pytest.mark.tier1
def test_lazy_child_marks_node_lazy():
    dd = pytest.importorskip("dask.dataframe")
    pd = pytest.importorskip("pandas")
    df = dd.from_pandas(pd.DataFrame({"x": np.arange(10.0),
                                      "y": np.arange(10.0)}), npartitions=1)
    lazy = qv.Scatter(df, x="x", y="y")
    assert node_is_lazy(lazy)  # premise: a dask-backed ref is lazy
    assert node_is_lazy(_s() * qv.Inset(lazy, rect=(0, 0, 0.4, 0.4)))
    assert not node_is_lazy(_s() * qv.Inset(_s(), rect=(0, 0, 0.4, 0.4)))


@pytest.mark.tier1
def test_negotiation_sees_inset_contents():
    # a RawFigure only renders on webengine; hiding one inside an inset must
    # still steer/inhibit negotiation ([D4] intersect-first via _elements_of)
    raw = qv.RawFigure({"data": [], "layout": {}}, kind="plotly")
    node = _s() * qv.Inset(raw, rect=(0, 0, 0.4, 0.4))
    assert raw in list(_elements_of(node))
    with pytest.raises(qv.errors.QtvizError):
        qv.core.compose.negotiate(node, "pyqtgraph")  # pg can't draw RawFigure


@pytest.mark.tier1
def test_inset_is_chrome_in_series_indexing():
    from qtviz.core.compose import series_index_map

    s1, s2 = _s(), _s()
    children = (s1, qv.Inset(_s(), rect=(0, 0, 0.4, 0.4)), s2)
    assert series_index_map(children) == [0, 0, 1]  # inset shifts nothing
    assert children[1].legend_entry(qv.Theme.light()) is None


# ── I2: rendering ────────────────────────────────────────────────────────────
@pytest.mark.tier2
@pytest.mark.parametrize("name", ["pyqtgraph", "matplotlib"])
def test_inset_renders_on_native_backends(name, qtbot):
    view = qv.View(_s() * qv.Inset(_zoom(), rect=(0.55, 0.55, 0.4, 0.4),
                                   label="zoom"), backend=name)
    qtbot.addWidget(view)
    inset_native = view.native([el for el in _elements_of(view.root)
                                if isinstance(el, qv.Inset)][0].id)
    assert inset_native is not None  # the live inset surface ([D53])


@pytest.mark.tier2
def test_mpl_inset_honors_child_surface(qtbot):
    view = qv.View(_s() * qv.Inset(_zoom(), rect=(0.5, 0.5, 0.45, 0.45),
                                   label="zoom"), backend="matplotlib")
    qtbot.addWidget(view)
    iax = view.pane("zoom").native
    assert tuple(iax.get_xlim()) == pytest.approx((2.0, 4.0))
    assert tuple(iax.get_ylim()) == pytest.approx((4.0, 16.0))


@pytest.mark.tier2
def test_pg_inset_tracks_parent_geometry(qtbot):
    view = qv.View(_s() * qv.Inset(_zoom(), rect=(0.5, 0.5, 0.4, 0.4),
                                   label="zoom"), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    iplot = view.pane("zoom").native
    w1 = iplot.geometry().width()
    view.resize(1200, 900)
    qtbot.waitUntil(lambda: iplot.geometry().width() > w1, timeout=2000)


@pytest.mark.tier2
def test_inset_in_a_grid_pane(qtbot):
    lay = qv.Layout.grid({
        "main": _s() * qv.Inset(_zoom(), rect=(0.5, 0.5, 0.4, 0.4), label="zoom"),
        "side": qv.Curve(D, x="x", y="y"),
    })
    view = qv.View(lay, backend="pyqtgraph")
    qtbot.addWidget(view)
    assert [p.label for p in view.panes] == ["main", "zoom", "side"]


@pytest.mark.tier2
def test_webengine_figure_skips_inset_with_warning():
    pytest.importorskip("plotly")
    from qtviz.backends.webengine._figure import build

    node = _s() * qv.Inset(_zoom(), rect=(0.5, 0.5, 0.4, 0.4), label="zoom")
    with pytest.warns(qv.errors.QtvizWarning, match="inset axes are not supported"):
        fig, source_ids = build(node, qv.Theme.light())
    assert len(source_ids) == 1  # the parent scatter only; no inset traces


# ── I3: insets are panes ─────────────────────────────────────────────────────
def _inset_view(backend, qtbot):
    view = qv.View(_s().opts(title="Overview")
                   * qv.Inset(_zoom(), rect=(0.55, 0.55, 0.4, 0.4), label="zoom"),
                   backend=backend)
    qtbot.addWidget(view)
    return view


@pytest.mark.tier2
@pytest.mark.parametrize("name", ["pyqtgraph", "matplotlib"])
def test_inset_pane_full_surface(name, qtbot):
    view = _inset_view(name, qtbot)
    assert [p.label for p in view.panes] == ["0", "zoom"]
    pane = view.pane("zoom")
    pane.set_range(x=(1.0, 3.0))
    assert pane.capture().x_range == pytest.approx((1.0, 3.0), rel=1e-3)
    assert len(pane.elements) == 1  # the zoom curve, not the parent scatter
    assert len(view.pane("0").elements) == 1  # the parent scatter, not the inset


@pytest.mark.tier2
def test_inset_window_survives_backend_switch(qtbot):
    view = _inset_view("pyqtgraph", qtbot)
    view.pane("zoom").set_range(x=(1.0, 3.0), y=(0.0, 9.0))
    view.set_backend("matplotlib")
    st = view.handle.capture_state()
    assert st.get("zoom").x_range == pytest.approx((1.0, 3.0), rel=1e-3)
    assert st.get("zoom").y_range == pytest.approx((0.0, 9.0), rel=1e-3)
    view.set_backend("pyqtgraph")  # and back
    assert view.pane("zoom").capture().x_range == pytest.approx(
        (1.0, 3.0), rel=1e-3)


@pytest.mark.tier2
@pytest.mark.parametrize("name", ["pyqtgraph", "matplotlib"])
def test_inset_events_carry_the_inset_pane(name, qtbot):
    view = _inset_view(name, qtbot)
    got: list = []
    view.on(qv.RangeEvent, got.append, throttle_ms=0, pane="zoom")
    view.pane("0").set_range(x=(0.0, 8.0))   # parent zoom — filtered out
    view.pane("zoom").set_range(x=(2.0, 3.0))
    assert got and all(e.pane == "zoom" for e in got)
    assert got[-1].source_id == "zoom"       # surface event: label as source


@pytest.mark.tier2
@pytest.mark.parametrize("name", ["pyqtgraph", "matplotlib"])
def test_inset_pane_export(name, qtbot, tmp_path):
    view = _inset_view(name, qtbot)
    view.resize(640, 480)
    out = view.pane("zoom").export("png", tmp_path / "zoom.png")
    assert out.exists() and out.stat().st_size > 0
