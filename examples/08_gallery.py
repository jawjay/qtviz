"""Element gallery — all eight Phase-1 element types in one grid.

Scatter · Curve · Bars · Histogram · Image · Heatmap · ErrorBars · Spread,
each in its own panel of a `Layout` grid.

Run:
    uv run python examples/08_gallery.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    rng = np.random.default_rng(5)
    x = np.linspace(0, 10, 200)
    line = {"x": x, "y": np.sin(x), "lo": np.sin(x) - 0.25, "hi": np.sin(x) + 0.25,
            "err": np.full(x.size, 0.2)}

    grid = {"gx": np.repeat(np.arange(12), 12), "gy": np.tile(np.arange(12), 12)}
    grid["gz"] = np.sin(grid["gx"] / 2) * np.cos(grid["gy"] / 2)
    image = np.outer(np.hanning(40), np.hanning(60))

    panels = [
        qv.Scatter({"x": rng.normal(size=600), "y": rng.normal(size=600)}, x="x", y="y", size=4),
        qv.Curve(line, x="x", y="y", line_width=2.0),
        qv.Bars({"cat": ["A", "B", "C", "D"], "v": [3.0, 7.0, 2.0, 5.0]}, x="cat", y="v"),
        qv.Histogram({"v": rng.normal(size=2000)}, value="v"),
        qv.Image(image, extent=(0, 0, 60, 40)),
        qv.Heatmap(grid, x="gx", y="gy", z="gz"),
        qv.ErrorBars(line, x="x", y="y", err="err"),
        qv.Spread(line, x="x", y_lo="lo", y_hi="hi"),
    ]
    layout = qv.Layout(panels, options=qv.LayoutOptions(cols=4))
    return qv.View(layout, theme=qv.Theme.dark())


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(1280, 560)
    view.setWindowTitle("qtviz — element gallery")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
