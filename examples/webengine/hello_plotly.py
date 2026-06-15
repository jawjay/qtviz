"""POC example — proves the architecture end-to-end.

What this demonstrates:
  1. A Plotly figure renders inside a Qt window via the QWebEngineView core.
  2. The "Randomize" button mutates the live plot in-place via PlotlyBackend.react()
     — no page reload (watch the title flicker free).
  3. Hover/click events from Plotly's JS side surface as typed Qt signals on
     the backend (PlotlyEvents.hover / .click).
  4. Bridge messages flow both directions over the qtwebplot.core transport.

Run:
    uv sync --extra plotly --extra dev
    uv run python examples/hello_plotly.py
"""

from __future__ import annotations

import random
import sys

import plotly.graph_objects as go
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qtwebplot.ext.plotly import (
    PlotlyBackend,
    PlotlyClickEvent,
    PlotlyHoverEvent,
)

from qtwebplot import PlotView


def make_figure(seed: int = 0) -> go.Figure:
    rng = random.Random(seed)
    n = 30
    x = list(range(n))
    y = [rng.gauss(0, 1) for _ in range(n)]
    fig = go.Figure(
        data=[go.Scatter(x=x, y=y, mode="lines+markers", name="trace 0")]
    )
    fig.update_layout(
        title=f"hello qtwebplot (seed={seed})",
        margin=dict(l=40, r=20, t=50, b=40),
        height=420,
    )
    return fig


class Demo(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot POC — Plotly")
        self.resize(960, 640)

        self._seed = 0
        self._backend = PlotlyBackend(make_figure(self._seed))
        self._plot = PlotView(self._backend)

        self._status = QLabel("connecting…")
        self._hover_label = QLabel("hover: —")
        self._click_label = QLabel("click: —")

        randomize_btn = QPushButton("Randomize (live react)")
        randomize_btn.clicked.connect(self._randomize)

        recolor_btn = QPushButton("Recolor (restyle)")
        recolor_btn.clicked.connect(self._recolor)

        retitle_btn = QPushButton("Retitle (relayout)")
        retitle_btn.clicked.connect(self._retitle)

        controls = QHBoxLayout()
        controls.addWidget(randomize_btn)
        controls.addWidget(recolor_btn)
        controls.addWidget(retitle_btn)
        controls.addStretch(1)

        labels = QHBoxLayout()
        labels.addWidget(self._status)
        labels.addStretch(1)
        labels.addWidget(self._hover_label)
        labels.addWidget(self._click_label)

        root = QVBoxLayout()
        root.addLayout(controls)
        root.addWidget(self._plot, 1)
        root.addLayout(labels)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        # Wire up signals.
        self._plot.ready.connect(lambda: self._status.setText("bridge ready ✓"))
        self._plot.received.connect(self._on_message)
        self._backend.events.hover.connect(self._on_hover)
        self._backend.events.click.connect(self._on_click)

    # ── plot mutations ───────────────────────────────────────────────────
    def _randomize(self) -> None:
        self._seed += 1
        self._backend.react(make_figure(self._seed))

    def _recolor(self) -> None:
        color = random.choice(["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e"])
        self._backend.restyle({"line.color": color, "marker.color": color}, indices=[0])

    def _retitle(self) -> None:
        self._backend.relayout({"title.text": f"retitled @ {random.randint(0, 999)}"})

    # ── event callbacks ──────────────────────────────────────────────────
    def _on_message(self, name: str, payload: object) -> None:
        # Useful as a peek at the raw bridge traffic.
        if name == "plotly.attached":
            self._status.setText("bridge ready ✓ (plotly attached)")

    def _on_hover(self, e: PlotlyHoverEvent) -> None:
        if not e.points:
            return
        p = e.points[0]
        self._hover_label.setText(f"hover: trace={p.trace_index} i={p.point_index} x={p.x} y={p.y}")

    def _on_click(self, e: PlotlyClickEvent) -> None:
        if not e.points:
            return
        p = e.points[0]
        self._click_label.setText(f"click: trace={p.trace_index} i={p.point_index} x={p.x} y={p.y}")


def main() -> int:
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
