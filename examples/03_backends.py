"""Backends — render the same Element through different backends, switch live.

One immutable `Scatter` renders through pyqtgraph (fast, OpenGL) or matplotlib
(publication-quality, vector export). `view.set_backend(...)` swaps at runtime,
preserving zoom and subscriptions. Click the button to toggle.

Run (matplotlib is an optional extra):
    uv run python examples/03_backends.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

import qtviz as qv


class BackendDemo(QWidget):
    def __init__(self) -> None:
        super().__init__()
        x = np.linspace(0, 10, 2000)
        data = {"x": x, "y": np.sin(x) * np.exp(-x / 12)}
        self._backends = list(qv.backends.list_available())  # e.g. pyqtgraph, matplotlib

        self.view = qv.View(qv.Scatter(data, x="x", y="y", size=4), backend=self._backends[0])
        self.button = QPushButton(self._label())
        self.button.clicked.connect(self._toggle)

        layout = QVBoxLayout(self)
        layout.addWidget(self.button)
        layout.addWidget(self.view)

    def _label(self) -> str:
        return f"backend: {self.view.handle.backend_name}  (click to switch)"

    def _toggle(self) -> None:
        if len(self._backends) < 2:
            return
        current = self.view.handle.backend_name
        nxt = next(b for b in self._backends if b != current)
        self.view.set_backend(nxt)
        self.button.setText(self._label())


def build():
    return BackendDemo()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    w = build()
    w.resize(820, 560)
    w.setWindowTitle("qtviz — backends")
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
