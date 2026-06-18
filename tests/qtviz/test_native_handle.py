"""Tier-2 — `handle.native(element_id)` / `View.native`, the R1 escape valve ([D53]).

Hands back the live backend primitive by element id so a developer can wire
backend-native interaction (ROIs, crosshairs, signals) the typed events don't
expose — without the live object ever touching the immutable Element."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("PySide6.QtWidgets")

pytestmark = pytest.mark.tier2

_TABLE = {"x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 0.5]}


def _backend(name):
    import qtviz.backends as B

    try:
        return B.get(name)
    except Exception:
        pytest.skip(f"{name} backend unavailable")


def test_pyqtgraph_native_returns_live_item(qtbot):
    import pyqtgraph as pg

    el = qv.Scatter(_TABLE, x="x", y="y")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert isinstance(handle.native(el.id), pg.ScatterPlotItem)
    assert handle.native("not-an-id") is None


def test_matplotlib_native_returns_artist(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.lines import Line2D

    el = qv.Curve(_TABLE, x="x", y="y")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert isinstance(handle.native(el.id), Line2D)


def test_overlay_each_element_is_reachable(qtbot):
    import pyqtgraph as pg

    a = qv.Scatter(_TABLE, x="x", y="y")
    b = qv.Curve(_TABLE, x="x", y="y")
    handle = _backend("pyqtgraph").render(a * b, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert isinstance(handle.native(a.id), pg.ScatterPlotItem)
    assert isinstance(handle.native(b.id), pg.PlotCurveItem)


def test_native_through_the_view(qtbot):
    import pyqtgraph as pg

    el = qv.Scatter(_TABLE, x="x", y="y")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    assert isinstance(view.native(el.id), pg.ScatterPlotItem)


def test_native_rebuilds_on_update(qtbot):
    import pyqtgraph as pg

    el = qv.Scatter(_TABLE, x="x", y="y")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id) is not None
    new = qv.Curve(_TABLE, x="x", y="y")
    handle.update(new)
    assert handle.native(el.id) is None  # stale id cleared
    assert isinstance(handle.native(new.id), pg.PlotCurveItem)


def test_composite_native_fans_out_to_panes():
    """A CompositeRenderHandle resolves an id by asking each pane (pure — no Qt)."""
    from qtviz.core.backend import CompositeRenderHandle, RenderHandle

    left = RenderHandle(None, SimpleNamespace(), "x")
    left._natives = {"a": "ITEM_A"}
    right = RenderHandle(None, SimpleNamespace(), "y")
    right._natives = {"b": "ITEM_B"}
    comp = CompositeRenderHandle(None, [left, right])
    assert comp.native("a") == "ITEM_A"
    assert comp.native("b") == "ITEM_B"
    assert comp.native("missing") is None
