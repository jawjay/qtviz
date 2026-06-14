"""Tier-2 — the Phase 1 gate example builds and brushes (milestone M4)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("pyqtgraph")

pytestmark = pytest.mark.tier2

_EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "dashboard_native.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("dashboard_native", _EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_dashboard_builds_and_brushes(qtbot):
    import qtviz.backends as B

    if "pyqtgraph" not in B.list_available():
        pytest.skip("pyqtgraph backend not registered")

    view, selections = _load_example().build()
    qtbot.addWidget(view)

    assert len(view.handle.plots) == 3            # Scatter + Curve + Histogram
    # brush the scatter panel → linked-brushing SelectEvent reaches the app
    view.handle.plots[0].getViewBox().select_bounds(-1.0, -5.0, 1.0, 5.0)
    assert selections and isinstance(selections[0], qv.SelectEvent)
