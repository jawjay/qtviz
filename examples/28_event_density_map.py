"""Event density map — 2M categorized events as a Datashaded raster you can inspect.

When a scatter has millions of points it overplots into a blob; Datashader aggregates
it into a screen-resolution density raster instead, **re-aggregating to the viewport as
you pan/zoom**. Here each event also has a categorical `kind`, so `color_by` produces a
per-category color blend (which land use dominates where).

Because a raster has no per-point identity, qtviz keeps the underlying per-pixel
aggregate: **hover anywhere and the event count under the cursor prints** (`HoverEvent.value`),
and the count stays correct as you zoom (the raster re-aggregates).

This builds an in-memory frame; swapping in a Dask frame
(`dd.read_parquet("s3://…/*.parquet")`) keeps the exact same call out-of-core — see
`examples/10_out_of_core.py`.

Run (needs the datashader extra):
    uv sync --extra datashader --extra dev
    uv run python examples/28_event_density_map.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd

import qtviz as qv

N = 2_000_000


def _city_events() -> pd.DataFrame:
    """A mixture of spatial clusters, each weighted toward a land-use category."""
    rng = np.random.default_rng(11)
    kinds = np.array(["residential", "commercial", "transit", "industrial"])
    # (center_x, center_y, spread, dominant-kind index)
    clusters = [(-2.0, 1.0, 0.9, 0), (1.5, 1.8, 0.6, 1), (0.2, -1.5, 1.2, 2), (3.0, -0.5, 0.5, 3)]
    xs, ys, ks = [], [], []
    per = N // len(clusters)
    for cx, cy, s, dom in clusters:
        xs.append(rng.normal(cx, s, per))
        ys.append(rng.normal(cy, s, per))
        # 70% the dominant kind, 30% a random other → realistic blend
        pick = np.where(rng.random(per) < 0.7, dom, rng.integers(0, 4, per))
        ks.append(kinds[pick])
    return pd.DataFrame({"lon": np.concatenate(xs), "lat": np.concatenate(ys),
                         "kind": pd.Categorical(np.concatenate(ks))})


def build(theme: qv.Theme | None = None):
    df = _city_events()
    scatter = qv.Scatter(df, x="lon", y="lat", color_by="kind", scale="datashader")
    view = qv.View(scatter, backend="pyqtgraph", theme=theme or qv.Theme.dark())

    def on_hover(e: qv.HoverEvent) -> None:
        if e.value is not None:
            print(f"events near ({e.x:.2f}, {e.y:.2f}): {e.value:.0f}")

    view.on(qv.HoverEvent, on_hover)
    return view


def main() -> int:
    if importlib.util.find_spec("datashader") is None:
        print("This example needs datashader: uv sync --extra datashader --extra dev")
        return 1
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    print(f"aggregating {N:,} categorized events into a density raster…")
    view = build()
    view.resize(820, 820)
    view.setWindowTitle("qtviz — event density map (hover for counts)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
