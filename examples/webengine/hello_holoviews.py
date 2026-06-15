"""POC example — HoloViews via the Bokeh renderer.

What this proves:
  - A HoloViews `Curve`, `Bars`, or composite renders inside Qt via the
    same PlotView surface used for Plotly and Bokeh.
  - Events (tap, selection) come from the underlying Bokeh model and
    surface as `BokehTapEvent` etc. through `backend.events`.
  - `set_figure(new_hv_object)` swaps the rendered figure cleanly.

Run:
    uv sync --extra holoviews --extra dev
    uv run python examples/hello_holoviews.py
"""

from __future__ import annotations

import random
import sys

import holoviews as hv
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qtwebplot.ext.bokeh import BokehTapEvent
from qtwebplot.ext.holoviews import HoloViewsBackend

from qtwebplot import PlotView

hv.extension("bokeh")


def make_curve(seed: int):
    rng = random.Random(seed)
    pts = [(i, rng.gauss(0, 1)) for i in range(30)]
    return hv.Curve(pts).opts(width=600, height=350, title=f"HoloViews curve (seed={seed})")


def make_bars(seed: int):
    rng = random.Random(seed)
    data = [(label, rng.randint(1, 10)) for label in "ABCDE"]
    return hv.Bars(data).opts(width=600, height=350, title="HoloViews bars")


def make_overlay(seed: int):
    return (make_curve(seed) * hv.Scatter(make_curve(seed).data).opts(size=8)).opts(
        title="Curve × Scatter overlay"
    )


class Demo(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot POC — HoloViews")
        self.resize(900, 600)

        self._seed = 0
        self._backend = HoloViewsBackend(make_curve(self._seed))
        self._plot = PlotView(self._backend)

        self._status = QLabel("connecting…")
        self._tap_label = QLabel("tap: —")

        curve_btn = QPushButton("Curve")
        bars_btn = QPushButton("Bars")
        overlay_btn = QPushButton("Overlay")
        randomize_btn = QPushButton("Re-seed")

        curve_btn.clicked.connect(lambda: self._set(make_curve(self._seed)))
        bars_btn.clicked.connect(lambda: self._set(make_bars(self._seed)))
        overlay_btn.clicked.connect(lambda: self._set(make_overlay(self._seed)))
        randomize_btn.clicked.connect(self._reseed)

        controls = QHBoxLayout()
        controls.addWidget(curve_btn)
        controls.addWidget(bars_btn)
        controls.addWidget(overlay_btn)
        controls.addWidget(randomize_btn)
        controls.addStretch(1)

        labels = QHBoxLayout()
        labels.addWidget(self._status)
        labels.addStretch(1)
        labels.addWidget(self._tap_label)

        root = QVBoxLayout()
        root.addLayout(controls)
        root.addWidget(self._plot, 1)
        root.addLayout(labels)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._plot.ready.connect(lambda: self._status.setText("bridge ready ✓"))
        self._backend.events.tap.connect(self._on_tap)

    def _set(self, obj) -> None:
        self._backend.set_figure(obj)
        # set_figure on a backend doesn't auto-re-render; PlotView does that
        # via set_backend or set_figure.
        self._plot.set_figure(obj)

    def _reseed(self) -> None:
        self._seed += 1
        self._set(make_curve(self._seed))

    def _on_tap(self, e: BokehTapEvent) -> None:
        if e.x is None:
            return
        self._tap_label.setText(f"tap: x={e.x:.2f} y={e.y:.2f}")


def main() -> int:
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
