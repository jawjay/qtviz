"""Composition — overlay with `*`, lay out side-by-side with `+`.

`a * b` overlays two elements on the same axes; `a + b` places them in
side-by-side panels. They compose, so `(scatter * curve) + hist` is one
expression describing the whole figure.

Run:
    uv run python examples/02_composition.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    x = np.linspace(0, 12, 600)
    rng = np.random.default_rng(1)
    signal = np.sin(x)
    data = {"x": x, "signal": signal, "noisy": signal + rng.normal(0, 0.25, x.size)}

    points = qv.Scatter(data, x="x", y="noisy", size=4, color="#5fa8ff")
    trend = qv.Curve(data, x="x", y="signal", color="#ff7f0e", line_width=2.0)
    hist = qv.Histogram(data, column="noisy", color="#7bd47b")

    figure = (points * trend) + hist          # overlay, then panel beside it
    return qv.View(figure, theme=qv.Theme.dark())


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(1000, 500)
    view.setWindowTitle("qtviz — composition")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
