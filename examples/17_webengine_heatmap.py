"""WebEngine heatmap — a tabular x/y/z Heatmap rendered as a Plotly heatmap.

W2 added renderers for all eight element types on the webengine backend. A
`Heatmap` (tabular x/y/z, pivoted to a grid) becomes a Plotly `heatmap` trace
with a Viridis colorscale — a different element family from the scatter/line
demos. Hover reads back the aggregated value at each cell.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and network for the Plotly CDN; it will not run headless.

Run:
    uv run python examples/17_webengine_heatmap.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    # a smooth 2-D field sampled on a regular grid, fed as tabular x/y/z
    xs = np.linspace(-3, 3, 60)
    ys = np.linspace(-3, 3, 60)
    gx, gy = np.meshgrid(xs, ys)
    z = np.exp(-(gx**2 + gy**2) / 4) * np.cos(gx * 2)
    data = {"x": gx.ravel(), "y": gy.ravel(), "z": z.ravel()}
    return qv.View(qv.Heatmap(data, x="x", y="y", z="z"), backend="webengine")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(720, 640)
    view.setWindowTitle("qtviz — webengine heatmap")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
