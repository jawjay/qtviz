"""Datashaded rasters that read like a finished plot — themed colors, a legend, and
a choice of aggregation (roadmap §8.5).

A datashaded `Scatter` used to render as a bare image: fixed default colors, no key.
Now the raster shades with the View's `Theme` and carries a legend, so a big-data plot
is publishable — and `agg=` picks what each pixel means:

    qv.Scatter(df, x, y, color_by="kind",      raster="datashader")             # blend → key
    qv.Scatter(df, x, y, color_by="elevation", raster="datashader", agg="max")  # max → bar

This lays the two side by side under `Theme.dark()`:
  - **left** — a per-category blend; the legend names each category in theme colors
    (the same swatches a native `color_by` scatter would use).
  - **right** — the *maximum* elevation falling in each pixel; a truthful **linear**
    colorbar (value aggregations shade linearly, unlike `eq_hist` density).

Pan/zoom either panel and it re-aggregates to the viewport — the legend/colorbar
follows (the colorbar's range tracks the visible window).

Run (needs the datashader extra):
    uv sync --extra datashader --extra dev
    uv run python examples/32_datashader_legends.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd

import qtviz as qv

N = 2_000_000


def _terrain_events() -> pd.DataFrame:
    """Spatial clusters, each leaning toward a land-use category, with a smooth
    elevation field (higher to the north-east) plus per-point noise."""
    rng = np.random.default_rng(7)
    kinds = np.array(["residential", "commercial", "transit", "industrial"])
    clusters = [(-2.0, 1.0, 0.9, 0), (1.5, 1.8, 0.6, 1), (0.2, -1.5, 1.2, 2), (3.0, -0.5, 0.5, 3)]
    xs, ys, ks = [], [], []
    per = N // len(clusters)
    for cx, cy, s, dom in clusters:
        xs.append(rng.normal(cx, s, per))
        ys.append(rng.normal(cy, s, per))
        pick = np.where(rng.random(per) < 0.7, dom, rng.integers(0, 4, per))
        ks.append(kinds[pick])
    lon, lat = np.concatenate(xs), np.concatenate(ys)
    elevation = 100.0 + 18.0 * (lon + lat) + rng.normal(0, 25.0, lon.size)
    return pd.DataFrame({"lon": lon, "lat": lat,
                         "kind": pd.Categorical(np.concatenate(ks)),
                         "elevation": elevation})


def build(theme: qv.Theme | None = None) -> qv.View:
    df = _terrain_events()
    by_category = qv.Scatter(df, x="lon", y="lat", color_by="kind", raster="datashader")
    max_elevation = qv.Scatter(df, x="lon", y="lat", color_by="elevation",
                               raster="datashader", agg="max")
    # `+` lays the two panels side by side; each is datashaded, themed, and legended.
    return qv.View(by_category + max_elevation, backend="pyqtgraph",
                   theme=theme or qv.Theme.dark())


def main() -> int:
    if importlib.util.find_spec("datashader") is None:
        print("This example needs datashader: uv sync --extra datashader --extra dev")
        return 1
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    print(f"aggregating {N:,} points → category blend (left) + max elevation (right)…")
    view = build()
    view.resize(1100, 620)
    view.setWindowTitle("qtviz — datashader legends & aggregation (zoom to re-aggregate)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
