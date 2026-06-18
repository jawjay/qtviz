"""Tier-2 — recommended options 0.2 wired actually reach the primitive ([D51]).

The conformance guard (`test_backend_conformance`) proves a honored option does
not *warn*; these prove it is actually *applied*. Backend-specific by necessity
(asserting an honor took effect means inspecting the native primitive)."""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("PySide6.QtWidgets")

pytestmark = pytest.mark.tier2

_TABLE = {"x": [0.0, 1.0, 2.0, 3.0], "y": [0.0, 1.0, 0.5, 1.5]}


def _backend(name):
    import qtviz.backends as B

    try:
        return B.get(name)
    except Exception:
        pytest.skip(f"{name} backend unavailable")


def _vb_items(handle, kind):
    return [it for plot in handle.plots for it in plot.getViewBox().addedItems
            if isinstance(it, kind)]


def test_pyqtgraph_scatter_honors_marker(qtbot):
    import pyqtgraph as pg

    handle = _backend("pyqtgraph").render(
        qv.Scatter(_TABLE, x="x", y="y", marker="square"), theme=qv.Theme.light()
    )
    qtbot.addWidget(handle.widget)
    items = _vb_items(handle, pg.ScatterPlotItem)
    assert items and items[0].opts["symbol"] == "s"


def test_pyqtgraph_curve_honors_line_style(qtbot):
    import pyqtgraph as pg
    from PySide6.QtCore import Qt

    handle = _backend("pyqtgraph").render(
        qv.Curve(_TABLE, x="x", y="y", line_style="dashed"), theme=qv.Theme.light()
    )
    qtbot.addWidget(handle.widget)
    curves = _vb_items(handle, pg.PlotCurveItem)
    assert curves and curves[0].opts["pen"].style() == Qt.DashLine


def test_matplotlib_curve_honors_line_style(qtbot):
    pytest.importorskip("matplotlib")
    handle = _backend("matplotlib").render(
        qv.Curve(_TABLE, x="x", y="y", line_style="dashed"), theme=qv.Theme.light()
    )
    qtbot.addWidget(handle.widget)
    lines = handle.axes[0].get_lines()
    assert lines and lines[0].get_linestyle() == "--"


def test_matplotlib_image_honors_interpolation(qtbot):
    pytest.importorskip("matplotlib")
    np = pytest.importorskip("numpy")
    el = qv.Image(np.arange(12.0).reshape(3, 4), bounds=(0, 0, 4, 3), interpolation="nearest")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    imgs = handle.axes[0].images
    assert imgs and imgs[0].get_interpolation() == "nearest"


def test_webengine_scatter_marker_symbol():
    """Pure (no display): the Plotly figure spec carries the mapped symbol."""
    from qtviz.backends.webengine import _figure

    fig, _ = _figure.build(qv.Scatter(_TABLE, x="x", y="y", marker="diamond"), qv.Theme.light())
    assert fig["data"][0]["marker"]["symbol"] == "diamond"
