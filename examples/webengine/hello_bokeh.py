"""POC example for the Bokeh extension — same shape as `hello_plotly.py` to
let you compare the architectures side-by-side.

What this proves about the design:
  - Identical PlotView + backend composition pattern as Plotly.
  - Different verbs (patch / stream / set_property) because Bokeh's
    incremental-update idiom is model-based, not figure-based — and that
    asymmetry sits naturally in the per-backend API.
  - JS->Python event flow uses CustomJS callbacks injected at figure-build
    time (the idiomatic Bokeh path), proving the bridge transport doesn't
    care how the JS side gets wired up.

Run:
    uv sync --extra bokeh --extra dev
    uv run python examples/hello_bokeh.py
"""

from __future__ import annotations

import random
import sys

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure as bokeh_figure
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qtwebplot.ext.bokeh import (
    BokehBackend,
    BokehSelectionEvent,
    BokehTapEvent,
)

from qtwebplot import PlotView

SOURCE_NAME = "main_src"


def make_figure(seed: int = 0):
    rng = random.Random(seed)
    n = 30
    x = list(range(n))
    y = [rng.gauss(0, 1) for _ in range(n)]
    src = ColumnDataSource(data={"x": x, "y": y}, name=SOURCE_NAME)

    p = bokeh_figure(
        height=420,
        sizing_mode="stretch_width",
        tools="pan,wheel_zoom,box_zoom,reset,tap,box_select",
        title=f"hello qtwebplot — bokeh (seed={seed})",
    )
    p.line("x", "y", source=src, line_width=2)
    p.scatter("x", "y", source=src, size=6)
    return p


class Demo(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot POC — Bokeh")
        self.resize(960, 640)

        self._seed = 0
        self._backend = BokehBackend(make_figure(self._seed))
        self._plot = PlotView(self._backend)

        self._status = QLabel("connecting…")
        self._tap_label = QLabel("tap: —")
        self._sel_label = QLabel("selection: —")

        randomize_btn = QPushButton("New data (patch CDS)")
        randomize_btn.clicked.connect(self._patch)

        stream_btn = QPushButton("Stream one point")
        stream_btn.clicked.connect(self._stream)

        controls = QHBoxLayout()
        controls.addWidget(randomize_btn)
        controls.addWidget(stream_btn)
        controls.addStretch(1)

        labels = QHBoxLayout()
        labels.addWidget(self._status)
        labels.addStretch(1)
        labels.addWidget(self._tap_label)
        labels.addWidget(self._sel_label)

        root = QVBoxLayout()
        root.addLayout(controls)
        root.addWidget(self._plot, 1)
        root.addLayout(labels)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._plot.ready.connect(lambda: self._status.setText("bridge ready ✓"))
        self._plot.received.connect(self._on_message)
        self._backend.events.tap.connect(self._on_tap)
        self._backend.events.selection.connect(self._on_selection)

        self._next_x = 30

    def _patch(self) -> None:
        self._seed += 1
        rng = random.Random(self._seed)
        n = 30
        data = {"x": list(range(n)), "y": [rng.gauss(0, 1) for _ in range(n)]}
        self._backend.patch(SOURCE_NAME, data)
        self._next_x = n

    def _stream(self) -> None:
        new = {"x": [self._next_x], "y": [random.gauss(0, 1)]}
        self._backend.stream(SOURCE_NAME, new, max_points=200)
        self._next_x += 1

    def _on_message(self, name: str, payload: object) -> None:
        if name == "bokeh.attached":
            self._status.setText("bridge ready ✓ (bokeh attached)")

    def _on_tap(self, e: BokehTapEvent) -> None:
        self._tap_label.setText(f"tap: x={e.x:.2f} y={e.y:.2f}" if e.x is not None else "tap: —")

    def _on_selection(self, e: BokehSelectionEvent) -> None:
        self._sel_label.setText(f"selection: {e.geometry}")


def main() -> int:
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
