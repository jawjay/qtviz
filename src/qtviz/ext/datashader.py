"""Datashader rasterization — the big-data path (Phase 4).

Aggregates millions–billions of points into a screen-resolution raster, so a
scatter that would overplot (or OOM) becomes a density image. Two properties
make this a strong foundation:

- **Backend-agnostic.** It produces an RGBA array + bounds; the result is a
  plain `Image`, so *every* backend renders a datashaded scatter for free. The
  routing (Scatter → Image) lives in the pipeline, not in any backend.
- **Out-of-core.** `channel_frame` keeps a dask source **lazy** — it assigns the
  channel accessors as columns on the dask frame and hands that to datashader,
  which aggregates partition-by-partition. Only the small raster is ever
  materialized; the points never all land in memory.

This module is the aggregation primitive. The viewport-driven re-aggregation
loop (re-rasterize on zoom at the widget's pixel size) is the next stage and
builds on `rasterize_points` via a per-backend raster target (see
`milestone-phase4-datashader.md` / D21).
"""

from __future__ import annotations

import numpy as np

from ..core.palette import _VIRIDIS
from ..data.accessor import resolve_expr

_FRAME_MODULES = ("dask.dataframe", "dask_expr", "pandas")


def channel_frame(ref, channels: dict):
    """Build a dataframe whose columns are the resolved channels. A dask source
    stays a (lazy) dask frame so datashader aggregates it out-of-core; anything
    else falls back to an eager pandas frame."""
    native = ref.native()
    if type(native).__module__.startswith(_FRAME_MODULES):
        cols = {role: resolve_expr(a, columns=native, native=native)
                for role, a in channels.items()}
        return native.assign(**cols)[list(channels)]
    import pandas as pd  # noqa: PLC0415

    return pd.DataFrame(ref.resolve_channels(channels))


def rasterize_points(
    frame, x: str, y: str, *,
    width: int, height: int,
    x_range=None, y_range=None,
    cmap=None, how: str = "eq_hist",
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Aggregate point density into an RGBA raster. Returns `(rgba, bounds)`
    where rgba is `(rows=y, cols=x, 4)` uint8 (origin = lower-left, row 0 = ymin)
    and bounds is `(xmin, ymin, xmax, ymax)`."""
    import datashader as ds  # noqa: PLC0415
    import datashader.transfer_functions as tf  # noqa: PLC0415

    canvas = ds.Canvas(plot_width=width, plot_height=height, x_range=x_range, y_range=y_range)
    agg = canvas.points(frame, x, y, agg=ds.count())  # x_range/y_range None → from data
    img = tf.shade(agg, cmap=list(cmap) if cmap else list(_VIRIDIS), how=how)
    rgba = img.data.view(np.uint8).reshape(img.shape + (4,)).copy()  # (y, x, 4)
    xs, ys = np.asarray(agg["x"].values), np.asarray(agg["y"].values)
    bounds = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
    return rgba, bounds


def rasterize_scatter(element, *, width: int, height: int, x_range=None, y_range=None):
    """Rasterize a Scatter's x/y channels (kept lazy for dask sources)."""
    frame = channel_frame(element.data, {"x": element.x, "y": element.y})
    return rasterize_points(
        frame, "x", "y", width=width, height=height, x_range=x_range, y_range=y_range,
    )
