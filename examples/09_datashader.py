"""Datashader — millions of points as a live density image.

A scatter with millions of points overplots into a blob (and strains the native
backends). Pass `raster="datashader"` and qtviz aggregates the points into a
screen-resolution density raster instead — and **re-aggregates to the visible
viewport at your widget's pixel size as you pan/zoom**, so the image sharpens
(Phase 4):

    qv.Scatter(data, x="x", y="y", raster="datashader")   # always rasterize
    qv.Scatter(data, x="x", y="y", raster="auto")          # rasterize past a threshold

The data here is a broad cloud sprinkled with a few tight sub-clusters: zoomed
out they're a smudge; zoom in and they resolve into structure, because each zoom
re-aggregates the underlying points to the window you're looking at.

Try it:
  - **wheel** to zoom, **drag** to pan → the raster re-aggregates to the viewport
  - watch the console for the live viewport (RangeEvent)

Run (needs the datashader extra):
    uv sync --extra datashader --extra dev
    uv run python examples/09_datashader.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv

N = 3_000_000


def _make_points() -> dict[str, np.ndarray]:
    """A broad gaussian cloud + a handful of tight clusters (fine structure that
    only resolves when you zoom in)."""
    rng = np.random.default_rng(0)
    cloud_n = N // 2
    x = [rng.normal(0, 3.0, cloud_n)]
    y = [rng.normal(0, 3.0, cloud_n)]
    centers = rng.uniform(-6, 6, size=(8, 2))
    per = (N - cloud_n) // len(centers)
    for cx, cy in centers:
        x.append(rng.normal(cx, 0.08, per))
        y.append(rng.normal(cy, 0.08, per))
    return {"x": np.concatenate(x), "y": np.concatenate(y)}


def build():
    data = _make_points()
    # raster="datashader" → the Scatter is aggregated to a raster off the GUI
    # thread, then re-aggregated to the viewport on every zoom/pan (4a + 4b).
    view = qv.View(qv.Scatter(data, x="x", y="y", raster="datashader"))
    view.on(
        qv.RangeEvent,
        lambda e: print(f"viewport x={e.x[0]:+.2f}..{e.x[1]:+.2f}  y={e.y[0]:+.2f}..{e.y[1]:+.2f}"),
        throttle_ms=200,
    )
    return view


def main() -> int:
    if importlib.util.find_spec("datashader") is None:
        print("This example needs datashader:  uv sync --extra datashader --extra dev")
        return 1
    app = QApplication.instance() or QApplication([])
    print(f"Aggregating {N:,} points — zoom in on a cluster to watch it resolve.")
    view = build()
    view.resize(760, 760)
    view.setWindowTitle("qtviz — datashader (zoom to re-aggregate)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
