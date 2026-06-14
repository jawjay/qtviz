"""WebEngine backend — the same Element, rendered through Plotly in a QWebEngineView.

qtviz's `webengine` backend turns an Element into a Plotly figure hosted in a Qt
WebEngine view, and bridges Plotly's interactions back as the *same* typed qtviz
events the native backends emit — so `view.on(PickEvent, ...)` works identically
whether the pane is pyqtgraph or webengine. Here a single `Scatter` (continuous
`color_by`, mapped to per-point colors) renders via webengine; the button swaps
the very same Element to a native backend and back.

  - **click a point**  → PickEvent
  - **box / lasso select** (Plotly modebar)  → SelectEvent (row indices)
  - **pan / zoom**  → RangeEvent (throttled)
Events print to the console.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and renders fully offline (JS bundled, no CDN). It will not run headless — a QWebEngineView
segfaults at teardown under offscreen Qt.

Run:
    uv run python examples/13_webengine.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

import qtviz as qv


def _on_pick(e) -> None:
    print(f"picked #{e.point_index} at ({e.x:.2f}, {e.y:.2f})")


def _on_select(e) -> None:
    print(f"selected {len(e.indices)} points  bounds={e.bounds}")


def _on_range(e) -> None:
    print(f"viewport x={e.x[0]:.2f}..{e.x[1]:.2f}")


class WebEngineDemo(QWidget):
    def __init__(self) -> None:
        super().__init__()
        rng = np.random.default_rng(7)
        n = 4000
        x = rng.normal(size=n)
        y = rng.normal(size=n)
        data = {"x": x, "y": y, "density": x**2 + y**2}

        scatter = qv.Scatter(data, x="x", y="y", color_by="density", size=6)
        self.view = qv.View(scatter, backend="webengine")
        self._native = next(
            (b for b in qv.backends.list_available() if b != "webengine"), "webengine"
        )

        self.view.on(qv.PickEvent, _on_pick)
        self.view.on(qv.SelectEvent, _on_select)
        self.view.on(qv.RangeEvent, _on_range)

        self.button = QPushButton(self._label())
        self.button.clicked.connect(self._toggle)

        layout = QVBoxLayout(self)
        layout.addWidget(self.button)
        layout.addWidget(self.view)

    def _label(self) -> str:
        return f"backend: {self.view.handle.backend_name}  (click to switch)"

    def _toggle(self) -> None:
        current = self.view.handle.backend_name
        self.view.set_backend(self._native if current == "webengine" else "webengine")
        self.button.setText(self._label())


def build():
    return WebEngineDemo()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    w = build()
    w.resize(860, 600)
    w.setWindowTitle("qtviz — webengine (Plotly)")
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
