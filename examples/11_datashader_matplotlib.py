"""Datashader on matplotlib — the same big-data path, a different backend.

Datashading is backend-agnostic: the aggregation is a pipeline step, so the same
`raster="datashader"` Scatter that pyqtgraph draws (example 09) renders through
matplotlib too — publication-quality, with vector export of the density raster.
And matplotlib re-aggregates to the viewport on zoom just like pyqtgraph: the
matplotlib navigation toolbar below gives mouse pan/zoom, and each zoom
re-rasterizes the points to the visible window at the canvas's pixel size.

Run (needs the datashader + matplotlib extras):
    uv sync --extra datashader --extra matplotlib --extra dev
    uv run python examples/11_datashader_matplotlib.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import qtviz as qv

N = 2_000_000


def _make_points() -> dict[str, np.ndarray]:
    """A broad cloud plus tight clusters — fine structure that resolves on zoom."""
    rng = np.random.default_rng(7)
    cloud = N // 2
    x = [rng.normal(0, 2.5, cloud)]
    y = [rng.normal(0, 2.5, cloud)]
    centers = rng.uniform(-5, 5, size=(6, 2))
    per = (N - cloud) // len(centers)
    for cx, cy in centers:
        x.append(rng.normal(cx, 0.06, per))
        y.append(rng.normal(cy, 0.06, per))
    return {"x": np.concatenate(x), "y": np.concatenate(y)}


class DatashaderMpl(QWidget):
    """A datashaded scatter on the matplotlib backend, with a nav toolbar so
    mouse pan/zoom drives the viewport re-aggregation."""

    def __init__(self) -> None:
        super().__init__()
        data = _make_points()
        self.view = qv.View(
            qv.Scatter(data, x="x", y="y", raster="datashader"),
            backend="matplotlib",
            theme=qv.Theme.dark(),
        )
        self._toolbar = None
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.view)
        # The canvas exists only after the async aggregation finishes; attach the
        # matplotlib toolbar once the handle is ready so mouse zoom works.
        self._attach_toolbar()

    def _attach_toolbar(self) -> None:
        if self.view.handle is not None:
            from matplotlib.backends.backend_qtagg import NavigationToolbar2QT  # noqa: PLC0415

            self._toolbar = NavigationToolbar2QT(self.view.handle.widget, self)
            self._layout.insertWidget(0, self._toolbar)
            return
        QTimer.singleShot(50, self._attach_toolbar)  # render still in flight — retry


def build():
    return DatashaderMpl()


def main() -> int:
    missing = [m for m in ("datashader", "matplotlib") if importlib.util.find_spec(m) is None]
    if missing:
        print(f"This example needs {', '.join(missing)}: "
              "uv sync --extra datashader --extra matplotlib --extra dev")
        return 1
    app = QApplication.instance() or QApplication([])
    print(f"Aggregating {N:,} points on the matplotlib backend — use the toolbar to zoom.")
    w = build()
    w.resize(780, 800)
    w.setWindowTitle("qtviz — datashader on matplotlib")
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
