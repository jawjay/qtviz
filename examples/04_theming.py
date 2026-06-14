"""Theming — light/dark themes, named colors, and a custom palette.

A `Theme` carries background / foreground / grid `Color`s and a `Palette`.
`Theme.light()` / `dark()` are built in; `Theme.from_qt_app()` matches the host
app. Colors accept names ("red"), hex ("#5fa8ff"), or rgb tuples; palettes are
registered by name and reused.

Run:
    uv run python examples/04_theming.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    # register a brand palette once; reuse it by name
    qv.palettes.register("brand", qv.Palette.from_hex(["#1f2937", "#ec4899", "#10b981"]))

    x = np.linspace(0, 10, 400)
    series = [qv.Curve({"x": x, "y": np.sin(x + p)}, x="x", y="y",
                       color=qv.palettes.get("brand")[i])
              for i, p in enumerate((0.0, 0.6, 1.2))]

    figure = series[0] * series[1] * series[2]              # overlay three curves
    theme = qv.Theme.dark()                                  # try Theme.light()
    return qv.View(figure, theme=theme)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(760, 520)
    view.setWindowTitle("qtviz — theming")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
