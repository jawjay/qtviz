"""Escape hatch — reach the live backend item with `view.native(id)` ([D53]).

qtviz's typed events (Range / Pick / Select / Hover / Tap) are a deliberately
portable lowest-common-denominator. When you need backend-native interaction they
don't model — a pyqtgraph crosshair, ROI, region selector, or a raw signal — call
`view.native(element.id)` to get the live primitive and wire it yourself:

    item = view.native(points.id)        # a pyqtgraph.ScatterPlotItem
    item.getViewBox().addItem(pg.InfiniteLine(...))

This is deliberately *non-portable*: the returned object is backend-specific, so
code using it opts out of "swap the backend, same behavior." The live object never
lives on the immutable Element — qtviz's purity / value-hashing is untouched; you
just opt into native power for one view.

Run:
    uv run python examples/33_native_escape_hatch.py
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

import qtviz as qv


def build():
    rng = np.random.default_rng(3)
    data = {"x": rng.normal(0.0, 1.0, 2000), "y": rng.normal(0.0, 1.0, 2000)}
    points = qv.Scatter(data, x="x", y="y", size=5, alpha=0.5, color="#5fa8ff")
    view = qv.View(points, backend="pyqtgraph", theme=qv.Theme.dark())

    # Escape hatch: grab the live pyqtgraph item and add a native crosshair —
    # there is no typed-event equivalent for "cursor lines that track the mouse".
    item = view.native(points.id)            # a pyqtgraph.ScatterPlotItem
    vb = item.getViewBox()
    pen = pg.mkPen("#ff7f0e", width=1)
    vline = pg.InfiniteLine(angle=90, pen=pen)
    hline = pg.InfiniteLine(angle=0, pen=pen)
    vb.addItem(vline, ignoreBounds=True)
    vb.addItem(hline, ignoreBounds=True)

    def move(scene_pos):
        if vb.sceneBoundingRect().contains(scene_pos):
            pt = vb.mapSceneToView(scene_pos)
            vline.setPos(pt.x())
            hline.setPos(pt.y())

    vb.scene().sigMouseMoved.connect(move)   # a raw pyqtgraph signal, not a qtviz event
    return view


def main() -> int:
    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(720, 600)
    view.setWindowTitle("qtviz — native escape hatch (crosshair via view.native)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
