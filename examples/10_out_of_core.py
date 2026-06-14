"""Out-of-core — a Dask DataFrame straight into a datashaded scatter.

qtviz's data layer is lazy-first: hand a `Scatter` a Dask DataFrame and it stays
lazy. With `scale="auto"` (or `"datashader"`) the points are aggregated
**partition-by-partition** — only the small raster is ever materialized, the full
table never lands in memory. The aggregation runs off the GUI thread, and each
pan/zoom re-aggregates just the visible window.

The demo builds the frame with `dd.from_pandas`, but the point is the seam: swap
in

    import dask.dataframe as dd
    ddf = dd.read_parquet("s3://bucket/huge/*.parquet")   # larger than RAM
    qv.Scatter(ddf, x="lon", y="lat", scale="auto")

and nothing else changes — same Element, same View.

Run (needs the datashader + dask extras):
    uv sync --extra datashader --extra dask --extra dev
    uv run python examples/10_out_of_core.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv

N = 4_000_000
PARTITIONS = 16  # the frame is processed one partition at a time


def build():
    import dask.dataframe as dd
    import pandas as pd

    rng = np.random.default_rng(1)
    frame = pd.DataFrame({
        "x": rng.normal(0, 2.5, N),
        "y": rng.normal(0, 2.5, N) + np.sin(rng.normal(0, 2.5, N)),
    })
    ddf = dd.from_pandas(frame, npartitions=PARTITIONS)  # lazy: never fully resolved

    # scale="auto" rasterizes here because the source is lazy (unknown size →
    # treated as potentially huge); the dask frame is aggregated out-of-core.
    return qv.View(qv.Scatter(ddf, x="x", y="y", scale="auto"), theme=qv.Theme.dark())


def main() -> int:
    missing = [m for m in ("datashader", "dask") if importlib.util.find_spec(m) is None]
    if missing:
        print(f"This example needs {', '.join(missing)}: "
              "uv sync --extra datashader --extra dask --extra dev")
        return 1
    app = QApplication.instance() or QApplication([])
    print(f"Aggregating a lazy {N:,}-row Dask frame in {PARTITIONS} partitions (out-of-core)…")
    view = build()
    view.resize(760, 760)
    view.setWindowTitle("qtviz — out-of-core (Dask + datashader)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
