"""WebEngine elements — several element types in one Plotly figure.

W2 gives the webengine backend a renderer for all eight element types. An
`Overlay` of different elements becomes one Plotly figure with one trace per
element (and two for a Spread band): here a confidence band (`Spread`) under a
fit line (`Curve`) under the noisy samples (`Scatter`) — a classic
"model + uncertainty" view, rendered entirely through Plotly in a Qt window.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and renders fully offline (JS bundled, no CDN); it will not run headless.

Run:
    uv run python examples/15_webengine_elements.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    rng = np.random.default_rng(1)
    x = np.linspace(0, 4 * np.pi, 240)
    fit = np.sin(x)
    data = {
        "x": x,
        "y": fit + rng.normal(0, 0.18, x.size),  # noisy samples
        "fit": fit,
        "lo": fit - 0.25,
        "hi": fit + 0.25,
    }

    band = qv.Spread(data, x="x", y_lo="lo", y_hi="hi", color="#5fa8ff", alpha=0.25)
    line = qv.Curve(data, x="x", y="fit", color="#1f6fff", line_width=2.5)
    points = qv.Scatter(data, x="x", y="y", color="#ff6b6b", size=5)

    return qv.View(band * line * points, backend="webengine", theme=qv.Theme.dark())


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(880, 560)
    view.setWindowTitle("qtviz — webengine elements (band + fit + points)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
