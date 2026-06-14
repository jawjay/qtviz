"""Mixed backends — a native pyqtgraph pane beside a webengine pane, one window.

A `Layout` whose panes resolve to different backends composes through qtviz's
LayoutHost: each pane is its own widget, but they share one merged event stream,
so a single `view.on(...)` hears events from either pane (W4). Here a fast native
pyqtgraph `Scatter` (OpenGL) sits beside the *same* points drawn as a Plotly
density-contour chart — a chart type qtviz doesn't natively model — hosted on the
webengine backend via `RawFigure`. `backend="auto"` resolves each pane on its own.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and renders fully offline (JS bundled, no CDN); the webengine pane will not run headless.

Run:
    uv run python examples/20_mixed_native_web.py
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    rng = np.random.default_rng(0)
    x = rng.normal(size=4000)
    y = x * 0.5 + rng.normal(size=4000)
    data = {"x": x, "y": y}

    native = qv.Scatter(data, x="x", y="y", size=4)              # → pyqtgraph (OpenGL)
    contour = go.Figure(go.Histogram2dContour(x=x, y=y, colorscale="Viridis"))
    web = qv.RawFigure(contour)                                  # → webengine (Plotly)

    view = qv.View(qv.Layout([native, web], kind="splitter"))    # backend="auto"
    view.on(qv.SelectEvent, lambda e: print(f"select from '{e.source_id}': {len(e.indices)} pts"))
    view.on(qv.RangeEvent, lambda e: print(f"range x={e.x[0]:.2f}..{e.x[1]:.2f}"))
    return view


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(1100, 560)
    view.setWindowTitle("qtviz — native + webengine, one event stream")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
