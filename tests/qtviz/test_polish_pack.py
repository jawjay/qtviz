"""Roadmap wave 1, increment 2 — bar labels + the series polish pack
([D98]/[D99]).

`Bars(bar_labels=)` via the [D86] format vocabulary; `Spread` grows the
horizontal orientation (`y`/`x_lo`/`x_hi`); `RefLine(slope, intercept)`;
dash tuples anywhere `line_style` is accepted; `marker_every`; five new
marker shapes — and the pre-existing pg wart where "triangle" pointed down
is fixed (pg "t1" points up like mpl "^"/Plotly "triangle-up").
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": np.linspace(0.0, 9.0, 30), "y": np.linspace(0.0, 3.0, 30)}
_B = {"cat": ["a", "b", "c"], "v": [3.0, 5.0, 2.0]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Curve(_T, x="x", y="y", line_style=(4.0, 2.0), marker="star", marker_every=5)
    qv.HLine(1.0, line_style=(6.0, 2.0))
    qv.RefLine(2.0, 1.0)
    qv.Bars(_B, x="cat", y="v", bar_labels=".1f")
    qv.Spread(_T, y="y", x_lo="x", x_hi="x")
    with pytest.raises(ValidationError):
        qv.Curve(_T, x="x", y="y", line_style=(4.0,))         # odd-length dash
    with pytest.raises(ValidationError):
        qv.Curve(_T, x="x", y="y", line_style="wavy")
    with pytest.raises(ValidationError):
        qv.Curve(_T, x="x", y="y", marker_every=0)
    with pytest.raises(ValidationError):
        qv.Bars(_B, x="cat", y="v", bar_labels="nope}")
    with pytest.raises(ValidationError):
        qv.Spread(_T, x="x", y_lo="y", x_hi="x")              # mixed orientations
    with pytest.raises(ValidationError):
        qv.Spread(_T, x="x", y_lo="y")                        # incomplete set


@pytest.mark.tier1
def test_webengine_polish_traces():
    from qtviz.backends.webengine import _figure

    light = qv.Theme.light()
    # dash tuple → px string
    tr = _figure.build_figure(
        qv.Curve(_T, x="x", y="y", line_style=(4.0, 2.0)), light)["data"][0]
    assert tr["line"]["dash"] == "4px,2px"
    # marker_every → thinned second trace
    trs = _figure.build_figure(
        qv.Curve(_T, x="x", y="y", marker="plus", marker_every=10), light)["data"]
    assert len(trs) == 2 and trs[0]["mode"] == "lines"
    assert trs[1]["mode"] == "markers" and len(trs[1]["x"]) == 3
    assert trs[1]["marker"]["symbol"] == "cross"   # Plotly's plus shape
    # bar labels
    bar = _figure.build_figure(
        qv.Bars(_B, x="cat", y="v", bar_labels="auto"), light)["data"][0]
    assert bar["text"] == ["3", "5", "2"] and bar["textposition"] == "outside"
    # horizontal spread
    spread = _figure.build_figure(
        qv.Spread(_T, y="y", x_lo="x", x_hi="x"), light)["data"]
    assert spread[1]["fill"] == "tonextx"
    # refline spans beyond the data range
    fig = _figure.build_figure(
        qv.Curve(_T, x="x", y="y") * qv.RefLine(0.5, 0.0), light)
    (shape,) = fig["layout"]["shapes"]
    assert shape["x0"] < 0.0 and shape["x1"] > 9.0
    assert shape["y1"] == pytest.approx(0.5 * shape["x1"])


@pytest.mark.tier1
def test_refline_drops_under_log():
    from qtviz.backends.webengine import _figure
    from qtviz.errors import QtvizWarning

    node = qv.Overlay(
        [qv.Curve({"x": [1.0, 10.0], "y": [1.0, 10.0]}, x="x", y="y"),
         qv.RefLine(1.0)],
        options=qv.OverlayOptions(y=qv.AxisSpec(scale="log")),
    )
    with pytest.warns(QtvizWarning, match="RefLine"):
        fig = _figure.build_figure(node, qv.Theme.light())
    assert not fig["layout"].get("shapes")


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_polish(qtbot):
    pytest.importorskip("matplotlib")
    b = _backend("matplotlib")
    curve = qv.Curve(_T, x="x", y="y", line_style=(5.0, 3.0), marker="star",
                     marker_every=10)
    rl = qv.RefLine(0.5, 0.0)
    handle = b.render(curve * rl, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    line = handle.native(curve.id)
    # mpl normalizes custom dashes to '--' + a stored pattern
    assert line.get_linestyle() == "--"
    assert tuple(line._unscaled_dash_pattern[1]) == (5.0, 3.0)
    assert line.get_marker() == "*" and line.get_markevery() == 10
    refline = handle.native(rl.id)
    assert refline is not None                     # an AxLine artist
    bars = qv.Bars(_B, x="cat", y="v", bar_labels=".1f")
    h2 = b.render(bars, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    texts = [t.get_text() for t in h2.axes[0].texts]
    assert texts == ["3.0", "5.0", "2.0"]
    spread = qv.Spread(_T, y="y", x_lo="x", x_hi="x")
    h3 = b.render(spread, theme=qv.Theme.light())
    qtbot.addWidget(h3.widget)
    assert len(h3.axes[0].collections) == 1        # fill_betweenx PolyCollection


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_polish(qtbot):
    import math

    import pyqtgraph as pg

    b = _backend("pyqtgraph")
    curve = qv.Curve(_T, x="x", y="y", line_style=(6.0, 3.0), marker="plus",
                     marker_every=10)
    rl = qv.RefLine(1.0, 0.0)
    handle = b.render(curve * rl, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(curve.id)
    assert isinstance(item, pg.PlotCurveItem)      # thinned markers → separate item
    assert item.opts["pen"].dashPattern() == [4.0, 2.0]   # points / width(1.5)
    assert handle.native(rl.id).angle == pytest.approx(math.degrees(math.atan(1.0)))


@pytest.mark.tier2
def test_pg_triangle_points_up_now(qtbot):
    handle = _backend("pyqtgraph").render(
        qv.Scatter({"x": [1.0], "y": [1.0]}, x="x", y="y", marker="triangle"),
        theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    items = [i for p in handle.plots for i in p.getViewBox().addedItems
             if hasattr(i, "opts") and "symbol" in getattr(i, "opts", {})]
    assert items[0].opts["symbol"] == "t1"         # up — was pg "t" (down)


@pytest.mark.tier2
def test_pg_bar_labels(qtbot):
    import pyqtgraph as pg

    el = qv.Bars(_B, x="cat", y="v", bar_labels="auto")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = [i for p in handle.plots for i in p.getViewBox().addedItems
             if isinstance(i, pg.TextItem)]
    assert sorted(t.textItem.toPlainText() for t in texts) == ["2", "3", "5"]
