"""Roadmap wave 1, increment 3 — per-point style channels ([D100]).

The `color_by` encoding pipeline generalizes beyond Scatter: `Bars(color_by=)`
colors each bar (categorical key or continuous ramp + colorbar), and
`Curve(color_by=)` colors per segment — categorical everywhere via the shared
core split, continuous as a matplotlib `LineCollection` (pg/webengine have no
gradient-polyline primitive and warn to a single color, value-level honesty).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": np.arange(8.0), "y": np.array([0.0, 1, 2, 1, 0, 1, 2, 3]),
      "state": np.array(["ok", "ok", "hot", "hot", "ok", "ok", "hot", "hot"]),
      "mag": np.linspace(0.0, 1.0, 8)}
_B = {"cat": ["a", "b", "c"], "v": [3.0, 5.0, 2.0], "kind": ["x", "y", "x"],
      "score": [0.1, 0.5, 0.9]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_validation_and_channels():
    from qtviz.errors import ValidationError

    c = qv.Curve(_T, x="x", y="y", color_by="state")
    assert "color" in c.channels()
    b = qv.Bars(_B, x="cat", y="v", color_by="kind")
    assert "color" in b.channels()
    with pytest.raises(ValidationError):
        qv.Curve(_T, x="x", y="y", color="#f00", color_by="state")
    with pytest.raises(ValidationError):
        qv.Curve(_T, x="x", y="y", color_by="state", marker="circle")
    with pytest.raises(ValidationError):
        qv.Bars(_B, x="cat", y="v", by="kind", color_by="kind")


@pytest.mark.tier1
def test_core_categorical_line_split():
    from qtviz.core._stats import categorical_line_split

    cats, parts = categorical_line_split(_T["x"], _T["y"], _T["state"])
    assert list(cats) == ["hot", "ok"]
    hot_x, _ = parts[0]
    ok_x, _ = parts[1]
    # segment i belongs to cats[i]: "ok" owns 0→1, 1→2, 4→5, 5→6
    assert np.isnan(ok_x[3]) and not np.isnan(ok_x[2])
    # run endpoints are kept on both sides so lines stay continuous
    assert not np.isnan(hot_x[2]) and not np.isnan(ok_x[1])


@pytest.mark.tier1
def test_color_by_opts_out_of_swatch_legend():
    theme = qv.Theme.light()
    assert qv.Curve(_T, x="x", y="y", color_by="state", label="L").legend_entry(theme) is None
    assert qv.Bars(_B, x="cat", y="v", color_by="kind", label="L").legend_entry(theme) is None


@pytest.mark.tier1
def test_webengine_color_by_traces():
    from qtviz.backends.webengine import _figure
    from qtviz.errors import QtvizWarning

    light = qv.Theme.light()
    traces = _figure.build_figure(
        qv.Curve(_T, x="x", y="y", color_by="state"), light)["data"]
    assert [t["name"] for t in traces] == ["hot", "ok"]
    assert all(t["showlegend"] for t in traces)
    bar = _figure.build_figure(
        qv.Bars(_B, x="cat", y="v", color_by="kind"), light)["data"][0]
    assert isinstance(bar["marker"]["color"], list)          # per-bar css
    cont = _figure.build_figure(
        qv.Bars(_B, x="cat", y="v", color_by="score"), light)["data"][0]
    assert "colorscale" in cont["marker"]                    # ramp + colorbar
    with pytest.warns(QtvizWarning, match="matplotlib-only"):
        solid = _figure.build_figure(
            qv.Curve(_T, x="x", y="y", color_by="mag"), light)["data"]
    assert len(solid) == 1                                   # honest fallback


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_curve_color_by(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.collections import LineCollection

    b = _backend("matplotlib")
    cat = qv.Curve(_T, x="x", y="y", color_by="state")
    h1 = b.render(cat, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    assert len(h1.native(cat.id)) == 2                       # one line per category
    assert [t.get_text() for t in h1.axes[0].get_legend().get_texts()] == ["hot", "ok"]
    cont = qv.Curve(_T, x="x", y="y", color_by="mag")
    h2 = b.render(cont, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    lc = h2.native(cont.id)
    assert isinstance(lc, LineCollection)
    assert len(lc.get_segments()) == len(_T["x"]) - 1
    assert h2.axes[0].figure.axes[-1] is not h2.axes[0]      # a colorbar axes exists


@pytest.mark.tier2
def test_mpl_bars_color_by(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Bars(_B, x="cat", y="v", color_by="kind")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    patches = handle.native(el.id).patches
    colors = {p.get_facecolor() for p in patches}
    assert len(colors) == 2                                  # two categories
    assert [t.get_text() for t in handle.axes[0].get_legend().get_texts()] == ["x", "y"]


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_curve_color_by(qtbot):
    import pyqtgraph as pg

    from qtviz.errors import QtvizWarning

    b = _backend("pyqtgraph")
    cat = qv.Curve(_T, x="x", y="y", color_by="state")
    h1 = b.render(cat, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    items = h1.native(cat.id)
    assert len(items) == 2 and all(isinstance(i, pg.PlotCurveItem) for i in items)
    cont = qv.Curve(_T, x="x", y="y", color_by="mag")
    with pytest.warns(QtvizWarning, match="matplotlib-only"):
        h2 = b.render(cont, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    assert isinstance(h2.native(cont.id), pg.PlotCurveItem)  # single solid line


@pytest.mark.tier2
def test_pg_bars_color_by(qtbot):
    el = qv.Bars(_B, x="cat", y="v", color_by="kind")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    brushes = handle.native(el.id).opts["brushes"]
    assert len(brushes) == 3
    assert brushes[0].color() == brushes[2].color()          # both "x" bars match
    assert brushes[0].color() != brushes[1].color()
