"""WebEngine export — save a webengine plot to PNG.

The webengine `RenderHandle` exports the rendered figure to PNG via the Qt
WebEngine view (`view.handle.export("png", path)`). Here we render a scatter,
let the Plotly page paint, then write a PNG next to this script and keep the
window open. (svg/pdf would need kaleido and currently raise.)

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and network for the Plotly CDN; it will not run headless.

Run:
    uv run python examples/16_webengine_export.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import qtviz as qv

_OUT = Path(__file__).resolve().parent / "webengine_export.png"


def build():
    rng = np.random.default_rng(5)
    x = rng.normal(size=3000)
    y = rng.normal(size=3000)
    data = {"x": x, "y": y, "d": x**2 + y**2}
    scatter = qv.Scatter(data, x="x", y="y", color_by="d", size=5)
    return qv.View(scatter, backend="webengine", theme=qv.Theme.dark())


def _export(view) -> None:
    out = view.handle.export("png", _OUT)
    print(f"wrote {out}  ({out.stat().st_size} bytes)")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(820, 560)
    view.setWindowTitle("qtviz — webengine export")
    view.show()
    # let the Plotly page load + paint before grabbing it
    QTimer.singleShot(1800, lambda: _export(view))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
