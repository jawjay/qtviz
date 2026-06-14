"""Native color_by / size_by + legends through the backends (Tier 2).

A `color_by` column maps to per-point colors (categorical key or continuous ramp)
and auto-adds a legend; `size_by` maps to per-point sizes. These assert the
wiring on both backends, not the pixels.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.data import pipeline  # noqa: E402

pytestmark = pytest.mark.tier2


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    n = 600
    return {
        "x": rng.normal(size=n),
        "y": rng.normal(size=n),
        "cat": np.array(["a", "b", "c"])[rng.integers(0, 3, n)],
        "z": rng.uniform(0.0, 100.0, n),
    }


def test_color_by_materializes_color_role(data):
    resolved = pipeline.resolve_node(qv.Scatter(data, x="x", y="y", color_by="cat"))
    np.testing.assert_array_equal(resolved.data.series("color"), np.asarray(data["cat"]))


# ── pyqtgraph ────────────────────────────────────────────────────────────────
def _pg_scatter(view):
    import pyqtgraph as pg

    plot = view.handle.plots[0]
    item = next(it for it in plot.items if isinstance(it, pg.ScatterPlotItem))
    return plot, item


def test_pyqtgraph_categorical_colors_and_legend(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", color_by="cat"), backend="pyqtgraph")
    qtbot.addWidget(view)
    plot, item = _pg_scatter(view)
    colors = {b.color().name() for b in item.data["brush"]}
    assert len(colors) == 3  # one per category
    assert plot.legend is not None and len(plot.legend.items) == 3


def test_pyqtgraph_continuous_legend_is_stepped(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", color_by="z"), backend="pyqtgraph")
    qtbot.addWidget(view)
    plot, item = _pg_scatter(view)
    assert len({b.color().name() for b in item.data["brush"]}) > 3  # a ramp, not 3 buckets
    assert plot.legend is not None and len(plot.legend.items) == 5  # 5 ramp stops


def test_pyqtgraph_size_by_varies_point_size(qtbot, data):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", size_by="z"), backend="pyqtgraph")
    qtbot.addWidget(view)
    _plot, item = _pg_scatter(view)
    assert len(np.unique(item.data["size"])) > 1


# ── matplotlib ───────────────────────────────────────────────────────────────
def test_matplotlib_categorical_legend(qtbot, data):
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", color_by="cat"), backend="matplotlib")
    qtbot.addWidget(view)
    ax = view.handle.axes[0]
    legend = ax.get_legend()
    assert legend is not None
    assert {t.get_text() for t in legend.get_texts()} == {"a", "b", "c"}


def test_matplotlib_continuous_adds_colorbar(qtbot, data):
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", color_by="z"), backend="matplotlib")
    qtbot.addWidget(view)
    fig = view.handle.axes[0].figure
    assert len(fig.axes) == 2  # main axes + colorbar axes
