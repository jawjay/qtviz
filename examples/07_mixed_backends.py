"""Mixed backends — a pyqtgraph pane beside a matplotlib pane, one window.

A `Layout` whose panes pick different backends (via `backend_hint`) renders as a
single Qt container (here a splitter). `view.on(...)` still sees one merged
event stream across both panes.

Run (needs the matplotlib extra):
    uv run python examples/07_mixed_backends.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    x = np.linspace(0, 10, 1500)
    rng = np.random.default_rng(4)
    data = {"x": x, "y": np.sin(x) + rng.normal(0, 0.15, x.size), "trend": np.sin(x)}

    fast = qv.Scatter(data, x="x", y="y", size=4, backend_hint="pyqtgraph")
    crisp = qv.Curve(data, x="x", y="trend", line_width=2.0, backend_hint="matplotlib")

    layout = qv.Layout([fast, crisp], kind="splitter")
    view = qv.View(layout, backend="pyqtgraph")
    view.on(qv.SelectEvent, lambda e: print(f"brushed {len(e.indices)} points"))
    return view


def main() -> int:
    if "matplotlib" not in qv.backends.list_available():
        print("This example needs the matplotlib extra: uv sync --extra matplotlib")
        return 1
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(1100, 520)
    view.setWindowTitle("qtviz — mixed backends (pyqtgraph + matplotlib)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
