"""Hello, qtviz — a scatter plot in a native Qt window.

The smallest possible qtviz program: describe an `Element`, drop it in a `View`
(a `QWidget`), show it. `backend="auto"` picks pyqtgraph.

Run:
    uv run python examples/01_hello.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build():
    x = np.linspace(0, 10, 500)
    rng = np.random.default_rng(0)
    data = {"x": x, "y": np.sin(x) + rng.normal(0, 0.1, x.size)}
    return qv.View(qv.Scatter(data, x="x", y="y"))


def main() -> None:
    # [D134]: the Qt ceremony is gone — and [D141]: building the View first is
    # safe; View ensures the QApplication exists.
    qv.show(build(), title="qtviz — hello", size=(720, 520))


if __name__ == "__main__":
    main()
