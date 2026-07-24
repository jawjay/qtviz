"""Tier-2 — mixed-backend host (milestone M5, spec §2.8/§3.7).

A Layout whose panes span backends (or a splitter/tabs/dock container) renders
as a CompositeRenderHandle: a Qt container of per-pane widgets with a merged
event bus, so one View.on(...) sees events from any pane. A homogeneous grid
the backend can host stays single-backend (keeping linked primitives).
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("pyqtgraph")
pytest.importorskip("matplotlib")

from PySide6.QtWidgets import QSplitter, QTabWidget, QWidget  # noqa: E402

from qtviz.backends.pyqtgraph.render import PgRenderHandle  # noqa: E402
from qtviz.core.backend import CompositeRenderHandle  # noqa: E402

pytestmark = pytest.mark.tier2


@pytest.fixture
def view(qtbot):
    import qtviz.backends as B

    if {"pyqtgraph", "matplotlib"} - set(B.list_available()):
        pytest.skip("need both pyqtgraph and matplotlib")

    def make(root):
        v = qv.View(root, backend="pyqtgraph")
        qtbot.addWidget(v)
        return v

    return make


def _mixed(table, kind="grid", **opts):
    return qv.Layout(
        [qv.Scatter(table, x="x", y="y", backend_hint="pyqtgraph"),
         qv.Curve(table, x="x", y="y", backend_hint="matplotlib")],
        kind=kind,
        options=qv.LayoutOptions(**opts) if opts else None,
    )


def test_mixed_splitter_is_composite(view, table):
    v = view(_mixed(table, kind="splitter"))
    assert isinstance(v.handle, CompositeRenderHandle)
    assert isinstance(v.handle.widget, QSplitter)
    assert [c.backend_name for c in v.handle.children] == ["pyqtgraph", "matplotlib"]


def test_mixed_grid_is_hosted(view, table):
    v = view(_mixed(table, kind="grid"))
    assert isinstance(v.handle, CompositeRenderHandle)
    assert isinstance(v.handle.widget, QWidget)


def test_tabs_use_labels(view, table):
    v = view(_mixed(table, kind="tabs", tab_labels=["A", "B"]))
    assert isinstance(v.handle.widget, QTabWidget)
    assert [v.handle.widget.tabText(i) for i in range(2)] == ["A", "B"]


def test_homogeneous_grid_stays_single_backend(view, table):
    # both panes default to pyqtgraph → no host; one handle that can link axes
    v = view(qv.Layout([qv.Scatter(table, x="x", y="y"), qv.Curve(table, x="x", y="y")]))
    assert isinstance(v.handle, PgRenderHandle)


def test_merged_bus_delivers_from_any_pane(view, table):
    v = view(_mixed(table, kind="splitter"))
    ranges, selects = [], []
    v.on(qv.RangeEvent, ranges.append)
    v.on(qv.SelectEvent, selects.append)
    # event from the pyqtgraph pane
    v.handle.children[0].plots[0].setXRange(2, 8, padding=0)
    # event from the matplotlib pane
    v.handle.children[1].select_bounds(0, 2.0, -1e9, 5.0, 1e9)
    v.handle.event_bus._drain()
    assert ranges and isinstance(ranges[-1], qv.RangeEvent)
    assert selects and selects[0].indices


def test_composite_dispose_tears_down_panes(view, table):
    v = view(_mixed(table, kind="splitter"))
    children = v.handle.children
    v.handle.dispose()
    assert all(c.widget is None for c in children)


def test_composite_export_png_works_vector_refuses(view, table, tmp_path):
    """Since 0.4 ([D72]) a composite exports one PNG (the grabbed container);
    a single vector surface across backends remains a non-goal ([D58])."""
    v = view(_mixed(table, kind="splitter"))
    out = v.handle.export("png", tmp_path / "composite.png")
    assert out.exists() and out.stat().st_size > 0
    with pytest.raises(NotImplementedError, match="per-pane"):
        v.handle.export("svg", tmp_path / "composite.svg")
