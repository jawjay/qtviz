"""Hello, qtviz — a scatter plot in a native Qt window.

The smallest possible qtviz program: describe an `Element`, drop it in a `View`
(a `QWidget`), show it. `backend="auto"` picks pyqtgraph.

Run:
    uv run python examples/01_hello.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    x = np.linspace(0, 10, 500)
    rng = np.random.default_rng(0)
    data = {"x": x, "y": np.sin(x) + rng.normal(0, 0.1, x.size)}
    return qv.View(qv.Scatter(data, x="x", y="y"))


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(720, 520)
    view.setWindowTitle("qtviz — hello")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
