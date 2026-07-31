"""Parity program increment 1 — series power ([D84]/[D85]/[D87]).

`Curve.step` (pre/mid/post) + `Curve.marker` on all three backends,
`Bars.orient="h"` actually wired (it warned-and-degraded on the native
backends, and grouped bars ignored it on webengine), and the surface
`grid=` toggle. Tier-1 covers validation + the pure Plotly figure spec;
tier-2 asserts the option reached the native primitive.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_TABLE = {"x": [0.0, 1.0, 2.0, 3.0], "y": [0.0, 1.0, 0.5, 1.5],
          "cat": ["a", "b", "a", "b"]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1: construction & validation ────────────────────────────────────────
pytestmark_tier1 = pytest.mark.tier1


@pytest.mark.tier1
def test_curve_step_and_marker_validate():
    from qtviz.errors import ValidationError

    qv.Curve(_TABLE, x="x", y="y", step="post", marker="square")  # ok
    with pytest.raises(ValidationError):
        qv.Curve(_TABLE, x="x", y="y", step="stairs")
    with pytest.raises(ValidationError):
        qv.Curve(_TABLE, x="x", y="y", marker="star")


@pytest.mark.tier1
def test_bars_stacked_requires_group():
    from qtviz.errors import ValidationError

    with pytest.raises(ValidationError):
        qv.Bars(_TABLE, x="cat", y="y", mode="stacked")  # no group → meaningless


@pytest.mark.tier1
def test_overlay_options_grid_defaults_on():
    assert qv.OverlayOptions().grid is True
    assert qv.OverlayOptions(grid=False).grid is False


# ── tier 1: webengine figure spec (pure, no display) ─────────────────────────
@pytest.mark.tier1
def test_webengine_curve_step_trace():
    from qtviz.backends.webengine import _figure

    el = qv.Curve(_TABLE, x="x", y="y", step="post")
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["line"]["shape"] == "hv"
    assert trace["type"] == "scatter"  # scattergl only supports linear/hv shapes


@pytest.mark.tier1
def test_webengine_curve_marker_trace():
    from qtviz.backends.webengine import _figure

    el = qv.Curve(_TABLE, x="x", y="y", marker="diamond")
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["mode"] == "lines+markers"
    assert trace["marker"]["symbol"] == "diamond"


@pytest.mark.tier1
def test_webengine_grouped_bars_horizontal():
    from qtviz.backends.webengine import _figure

    el = qv.Bars(_TABLE, x="cat", y="y", group="cat", orient="h")
    traces = _figure.build_figure(el, qv.Theme.light())["data"]
    assert all(tr["orientation"] == "h" for tr in traces)
    assert all(isinstance(tr["y"][0], str) for tr in traces)  # categories on y


@pytest.mark.tier1
def test_webengine_grid_off():
    from qtviz.backends.webengine import _figure

    node = qv.Overlay([qv.Curve(_TABLE, x="x", y="y")],
                      options=qv.OverlayOptions(grid=False))
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    assert layout["xaxis"]["showgrid"] is False
    assert layout["yaxis"]["showgrid"] is False


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_curve_step_and_marker(qtbot):
    pytest.importorskip("matplotlib")
    handle = _backend("matplotlib").render(
        qv.Curve(_TABLE, x="x", y="y", step="post", marker="square"),
        theme=qv.Theme.light(),
    )
    qtbot.addWidget(handle.widget)
    (line,) = handle.axes[0].get_lines()
    assert line.get_drawstyle() == "steps-post"
    assert line.get_marker() == "s"


@pytest.mark.tier2
def test_mpl_bars_horizontal(qtbot):
    pytest.importorskip("matplotlib")
    handle = _backend("matplotlib").render(
        qv.Bars({"x": [0.0, 1.0], "y": [3.0, 1.0]}, x="x", y="y", orient="h"),
        theme=qv.Theme.light(),
    )
    qtbot.addWidget(handle.widget)
    patches = handle.axes[0].patches
    # horizontal: the bar length lives on width, thickness on height
    assert {p.get_width() for p in patches} == {3.0, 1.0}
    assert all(p.get_height() < 1.0 for p in patches)


@pytest.mark.tier2
def test_mpl_grouped_bars_horizontal(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Bars(_TABLE, x="cat", y="y", group="cat", orient="h")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["a", "b"]
    assert all(p.get_height() < 1.0 for p in ax.patches)


@pytest.mark.tier2
def test_mpl_grid_off(qtbot):
    pytest.importorskip("matplotlib")
    node = qv.Overlay([qv.Curve(_TABLE, x="x", y="y")],
                      options=qv.OverlayOptions(grid=False))
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert not any(gl.get_visible() for gl in ax.xaxis.get_gridlines())


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_curve_step_post(qtbot):
    el = qv.Curve(_TABLE, x="x", y="y", step="post")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert item.opts["stepMode"] == "left"  # pg "left" == data "post"


@pytest.mark.tier2
def test_pg_curve_step_mid_uses_edges(qtbot):
    el = qv.Curve(_TABLE, x="x", y="y", step="mid")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert item.opts["stepMode"] == "center"
    x, y = item.getData()
    assert len(x) == len(y) + 1  # center mode takes bin edges


@pytest.mark.tier2
def test_pg_curve_marker(qtbot):
    import pyqtgraph as pg

    el = qv.Curve(_TABLE, x="x", y="y", marker="square")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert isinstance(item, pg.PlotDataItem)
    assert item.opts["symbol"] == "s"


@pytest.mark.tier2
def test_pg_bars_horizontal(qtbot):
    el = qv.Bars({"x": [0.0, 1.0], "y": [3.0, 1.0]}, x="x", y="y", orient="h")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert list(np.asarray(item.opts["x1"], dtype=float)) == [3.0, 1.0]
    assert item.opts.get("height") is not None  # thickness on the y axis


@pytest.mark.tier2
def test_pg_grid_off(qtbot):
    node = qv.Overlay([qv.Curve(_TABLE, x="x", y="y")],
                      options=qv.OverlayOptions(grid=False))
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.plots[0].getAxis("bottom").grid is False


# ── streaming ladder stays honest with the new curve shapes ─────────────────
@pytest.mark.tier2
def test_pg_set_element_data_marker_curve(qtbot):
    """A marker curve renders as PlotDataItem — the in-place write must still
    work (rung 1 of the fallback ladder, [D77])."""
    el = qv.Curve(_TABLE, x="x", y="y", marker="circle")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ok = handle.set_element_data(
        el.id, {"x": np.array([0.0, 1.0]), "y": np.array([5.0, 6.0])})
    assert ok
    x, _y = handle.native(el.id).getData()
    assert len(x) == 2


@pytest.mark.tier2
def test_pg_set_element_data_mid_step_declines(qtbot):
    """center-step needs n+1 edges — rung 1 must decline (return False), not
    write mismatched arrays."""
    el = qv.Curve(_TABLE, x="x", y="y", step="mid")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.set_element_data(
        el.id, {"x": np.array([0.0, 1.0]), "y": np.array([5.0, 6.0])}) is False
