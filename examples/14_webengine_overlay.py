"""WebEngine overlay — two Scatter series become two Plotly traces, one figure.

An `Overlay` (`a * b`) renders as multiple traces in a single Plotly figure on
the webengine backend. Each trace remembers which Element it came from, so a
PickEvent carries the originating series' id — the click is routed back to the
right series, not just "some point in the figure".

Give the series explicit ids and watch the console: clicking a point prints the
series it belongs to.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and renders fully offline (JS bundled, no CDN); it will not run headless.

Run:
    uv run python examples/14_webengine_overlay.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    rng = np.random.default_rng(3)
    a = {"x": rng.normal(-1.5, 0.5, 1500), "y": rng.normal(-1.5, 0.5, 1500)}
    b = {"x": rng.normal(1.5, 0.5, 1500), "y": rng.normal(1.5, 0.5, 1500)}

    cluster_a = qv.Scatter(a, x="x", y="y", color="#5fa8ff", size=6, id="cluster A")
    cluster_b = qv.Scatter(b, x="x", y="y", color="#ff6b6b", size=6, id="cluster B")

    view = qv.View(cluster_a * cluster_b, backend="webengine")
    view.on(qv.PickEvent, lambda e: print(f"picked '{e.source_id}'  point #{e.point_index}"))
    return view


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(760, 600)
    view.setWindowTitle("qtviz — webengine overlay")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
