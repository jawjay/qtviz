"""Linked-event coordination demo.

What this proves:
  - `PlotGrid.link(source=..., event=..., to=[...], handler=...)` forwards
    a JS->Python event from one view to a callback that acts on the
    target backends. Source and target can be any combination of backends.
  - Linked plots stay in sync without the user wiring signal-by-signal
    plumbing.
  - The link is auto-torn-down when either endpoint is removed from the grid.

Three live links:
  - Plotly hover on top-left   → Plotly relayout title on top-right.
  - Plotly click on top-left   → Bokeh patch on bottom-left (highlights point).
  - Bokeh tap on bottom-right  → Plotly relayout title on top-left.

Run:
    uv sync --extra plotly --extra bokeh --extra dev
    uv run python examples/linked_plots.py
"""

from __future__ import annotations

import sys

import plotly.graph_objects as go
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure as bokeh_figure
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from qtwebplot import PlotGrid
from qtwebplot.ext.bokeh import BokehBackend
from qtwebplot.ext.plotly import PlotlyBackend


def make_plotly(title: str) -> go.Figure:
    fig = go.Figure(
        data=go.Scatter(
            x=list(range(20)),
            y=[(i - 10) ** 2 / 10 for i in range(20)],
            mode="lines+markers",
            name="x²/10",
        )
    )
    fig.update_layout(title=title, margin=dict(l=40, r=20, t=40, b=30), height=320)
    return fig


def make_bokeh(title: str, name: str):
    src = ColumnDataSource(
        data={"x": list(range(20)), "y": [(i - 10) ** 2 / 10 for i in range(20)]},
        name=name,
    )
    p = bokeh_figure(
        height=320,
        sizing_mode="stretch_width",
        tools="pan,wheel_zoom,box_zoom,reset,tap",
        title=title,
    )
    p.line("x", "y", source=src, line_width=2)
    p.scatter("x", "y", source=src, size=7, name=name + "-scatter")
    return p


class Demo(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot — linked plots")
        self.resize(1100, 800)

        # 2x2 grid: (Plotly, Plotly, Bokeh, Bokeh)
        self._backends = [
            PlotlyBackend(make_plotly("Source (Plotly)")),
            PlotlyBackend(make_plotly("Title follows hover")),
            BokehBackend(make_bokeh("Patch follows click", name="src_bl")),
            BokehBackend(make_bokeh("Source (Bokeh) — tap me", name="src_br")),
        ]
        self._grid = PlotGrid(self._backends, cols=2, spacing=6)

        info = QLabel(
            "Hover top-left → top-right title updates.\n"
            "Click top-left → bottom-left point highlights.\n"
            "Tap bottom-right → top-left title updates."
        )
        info.setStyleSheet("padding: 6px;")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(info)
        layout.addWidget(self._grid, 1)
        self.setCentralWidget(central)

        self._wire_links()

    def _wire_links(self) -> None:
        # Plotly hover on view 0 → Plotly relayout title on view 1.
        def on_hover_to_plotly(target_backend, payload):
            pts = (payload or {}).get("points") or []
            if not pts:
                return
            p = pts[0]
            target_backend.relayout(
                {"title.text": f"hover x={p.get('x')} y={p.get('y')}"}
            )

        self._grid.link(
            source=0,
            event="plotly.hover",
            to=1,
            handler=on_hover_to_plotly,
        )

        # Plotly click on view 0 → Bokeh patch on view 2 (highlight that x).
        def on_click_to_bokeh(target_backend, payload):
            pts = (payload or {}).get("points") or []
            if not pts:
                return
            clicked_x = pts[0].get("x")
            # Recompute y, mark the clicked x with a tall spike, others = original.
            xs = list(range(20))
            ys = [(i - 10) ** 2 / 10 for i in xs]
            for i, x in enumerate(xs):
                if x == clicked_x:
                    ys[i] = 20.0
            target_backend.patch("src_bl", {"x": xs, "y": ys})

        self._grid.link(
            source=0,
            event="plotly.click",
            to=2,
            handler=on_click_to_bokeh,
        )

        # Bokeh tap on view 3 → Plotly relayout title on view 0.
        def on_tap_to_plotly(target_backend, payload):
            x = (payload or {}).get("x")
            y = (payload or {}).get("y")
            if x is None or y is None:
                return
            target_backend.relayout(
                {"title.text": f"tapped from bottom-right: x={x:.2f}, y={y:.2f}"}
            )

        self._grid.link(
            source=3,
            event="bokeh.tap",
            to=0,
            handler=on_tap_to_plotly,
        )


def main() -> int:
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
