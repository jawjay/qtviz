"""qtviz native dashboard — the Phase 1 acceptance gate.

Three panels (Scatter + Histogram + Curve), a shared X axis, a dark theme,
and linked brushing — 100% pyqtgraph, no JS, no webengine. Shift-drag in the
scatter to brush; the SelectEvent reports the brushed row indices, which a
real app would use to filter the other panels.

Run:
    uv run python examples/dashboard_native.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build(theme: qv.Theme | None = None):
    """Construct the dashboard View. Returns (view, selections) where
    `selections` accumulates SelectEvents (the linked-brushing hook)."""
    rng = np.random.default_rng(0)
    t = np.linspace(0.0, 10.0, 2000)
    signal = np.sin(t)
    data = {"t": t, "signal": signal, "noisy": signal + rng.normal(0, 0.25, t.size)}

    scatter = qv.Scatter(data, x="t", y="noisy", size=4, color="#5fa8ff")
    curve = qv.Curve(data, x="t", y="signal", color="#ff7f0e", line_width=2.0)
    hist = qv.Histogram(data, column="noisy", color="#7bd47b")

    layout = qv.Layout([scatter, curve, hist], options=qv.LayoutOptions(cols=3, link_x=True))
    view = qv.View(layout, backend="pyqtgraph", theme=theme or qv.Theme.dark())

    selections: list[qv.SelectEvent] = []
    view.on(qv.SelectEvent, selections.append)
    return view, selections


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    view, _ = build()
    view.resize(1200, 400)
    view.setWindowTitle("qtviz — native dashboard")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
