"""Mosaic layouts — spanning panes from an ASCII plan ([D108], wave 1.3).

`Layout.mosaic("AAB\\nCCB", ...)` places panes on a grid the way
matplotlib's `subplot_mosaic` does: repeated letters span cells, `.` leaves a
hole. `LayoutOptions(width_ratios=, height_ratios=)` size the tracks and
`title=` renders a real figure-level suptitle. Here: a wide price curve (A)
over a wide annotated heatmap (C), with one tall distribution panel (B)
spanning both rows on the right.

Run:
    uv run python examples/36_mosaic_layout.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv

BACKEND = "matplotlib"

rng = np.random.default_rng(11)
t = np.linspace(0.0, 30.0, 400)
price = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, t.size)))

# A — wide price curve with a reference annotation
a = qv.Overlay(
    [qv.Curve({"t": t, "p": price}, x="t", y="p", label="price"),
     qv.HLine(float(price.mean()), line_style="dashed", label="mean")],
    options=qv.OverlayOptions(title="Price"),
)

# B — tall return distribution, spanning both rows
returns = {"r": np.diff(np.log(price)) * 100}
b = (qv.Histogram(returns, value="r", bins="fd")).opts(title="Returns (%)")

# C — wide annotated activity heatmap ([D113])
hx, hy = np.meshgrid(np.arange(10.0), np.arange(3.0))
c = qv.Overlay(
    [qv.Heatmap({"hour": hx.ravel(), "desk": hy.ravel(),
                 "vol": (rng.random(30) * 90 + 10).round()},
                x="hour", y="desk", z="vol", annotate=".0f")],
    options=qv.OverlayOptions(title="Volume by desk"),
)

root = qv.Layout.mosaic(
    "AAB\nCCB", A=a, B=b, C=c,
    options=qv.LayoutOptions(width_ratios=[1.0, 1.0, 0.8],
                             title="Mosaic: spanning panes + suptitle"),
)


def build() -> qv.View:
    return qv.View(root, backend=BACKEND)


def main() -> None:
    app = QApplication([])
    view = build()
    view.resize(1100, 620)
    view.setWindowTitle("qtviz — mosaic layout")
    view.show()
    app.exec()


if __name__ == "__main__":
    main()
