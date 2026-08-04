"""Axis-surface seam, Phase A — `OverlayOptions` title / axis-labels reach every
backend (see design/axis-surface-feasibility.md).

Before this seam, `OverlayOptions.title/x_label/y_label` were defined but read by
no backend. These assert the wiring (the text on the rendered surface), not the
pixels. Scales / limits / tick-formatting are later phases.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")


@pytest.fixture
def data():
    x = np.linspace(0, 10, 50)
    return {"x": x, "y": np.sin(x)}


def _surface(node, **opts):
    return qv.Overlay([node], options=qv.OverlayOptions(**opts))


# ── core normalizer (pure) ───────────────────────────────────────────────────
@pytest.mark.tier1
def test_surface_of_returns_overlay_options(data):
    from qtviz.core.compose import surface_of

    el = qv.Scatter(data, x="x", y="y")
    # bare element → defaults
    assert isinstance(surface_of(el), qv.OverlayOptions)
    assert surface_of(el).title is None
    # overlay → its own options
    ov = _surface(el, title="T", x="X", y="Y")
    assert surface_of(ov).title == "T"
    assert surface_of(ov) is ov.options


# ── pyqtgraph ────────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pyqtgraph_applies_title_and_labels(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    node = _surface(qv.Scatter(data, x="x", y="y"), title="Sine", x="t", y="v")
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    plot = view.handle.plots[0]
    assert plot.titleLabel.text == "Sine"
    assert plot.getAxis("bottom").labelText == "t"
    assert plot.getAxis("left").labelText == "v"


@pytest.mark.tier2
def test_pyqtgraph_bare_element_has_no_title(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle.plots[0].titleLabel.text == ""


# ── matplotlib ───────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_matplotlib_applies_title_and_labels(qtbot, data):
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib not registered")
    node = _surface(qv.Scatter(data, x="x", y="y"), title="Sine", x="t", y="v")
    view = qv.View(node, backend="matplotlib")
    qtbot.addWidget(view)
    ax = view.handle.axes[0]
    assert ax.get_title() == "Sine"
    assert ax.get_xlabel() == "t"
    assert ax.get_ylabel() == "v"


@pytest.mark.tier2
def test_matplotlib_per_pane_labels_in_layout(qtbot, data):
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib not registered")
    left = _surface(qv.Curve(data, x="x", y="y"), title="L", x="lx")
    right = _surface(qv.Scatter(data, x="x", y="y"), title="R", x="rx")
    view = qv.View(qv.Layout([left, right]), backend="matplotlib")
    qtbot.addWidget(view)
    titles = {ax.get_title() for ax in view.handle.axes}
    assert titles == {"L", "R"}  # each pane keeps its own surface options


# ── webengine (pure figure spec; no display) ─────────────────────────────────
@pytest.mark.tier1
def test_webengine_layout_carries_title_and_labels(data):
    from qtviz.backends.webengine import _figure

    node = _surface(qv.Scatter(data, x="x", y="y"), title="Sine", x="t", y="v")
    fig = _figure.build_figure(node, qv.Theme.light())
    layout = fig["layout"]
    assert layout["title"]["text"] == "Sine"
    assert layout["xaxis"]["title"]["text"] == "t"
    assert layout["yaxis"]["title"]["text"] == "v"


@pytest.mark.tier1
def test_webengine_axis_titles_are_independent(data):
    """Regression: x/y axis dicts must not share one `title` object, else an
    x-only label leaks onto the y axis."""
    from qtviz.backends.webengine import _figure

    node = _surface(qv.Scatter(data, x="x", y="y"), x="only-x")
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    assert layout["xaxis"]["title"].get("text") == "only-x"
    assert "text" not in layout["yaxis"]["title"]
    assert "title" not in layout  # no figure title set


@pytest.mark.tier1
def test_webengine_bare_element_has_no_titles(data):
    from qtviz.backends.webengine import _figure

    layout = _figure.build_figure(qv.Scatter(data, x="x", y="y"), qv.Theme.light())["layout"]
    assert "title" not in layout
    assert "text" not in layout["xaxis"]["title"]
    assert "text" not in layout["yaxis"]["title"]


# ── surface background ───────────────────────────────────────────────────────
# `OverlayOptions.background` was defined but read by no backend (same defect
# shape as the pre-seam title/labels this file opens with). It sets the *plot
# area* — the theme keeps the figure/widget chrome.
@pytest.mark.tier2
def test_matplotlib_applies_surface_background(qtbot, data):
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib not registered")
    from matplotlib.colors import to_rgba

    node = _surface(qv.Scatter(data, x="x", y="y"), background="#123456")
    view = qv.View(node, backend="matplotlib")
    qtbot.addWidget(view)
    assert view.handle.axes[0].get_facecolor() == to_rgba("#123456")


@pytest.mark.tier2
def test_pyqtgraph_applies_surface_background(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    from qtviz.core.color import Color

    node = _surface(qv.Scatter(data, x="x", y="y"), background="#123456")
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    vb = view.handle.plots[0].getViewBox()
    assert vb.state["background"] == Color("#123456").qt()


@pytest.mark.tier2
def test_pyqtgraph_default_surface_has_no_background_override(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle.plots[0].getViewBox().state["background"] is None


@pytest.mark.tier1
def test_webengine_layout_carries_surface_background(data):
    from qtviz.backends.webengine import _figure

    node = _surface(qv.Scatter(data, x="x", y="y"), background="#123456")
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    assert layout["plot_bgcolor"] == "rgb(18,52,86)"
    # the figure chrome stays on the theme
    assert layout["paper_bgcolor"] == "rgb(255,255,255)"
