"""Datashader rasterization — the big-data path (Phase 4).

Aggregates millions–billions of points/lines into a screen-resolution raster, so
a plot that would overplot (or OOM) becomes a density (or value) image. Two
properties make this a strong foundation:

- **Backend-agnostic.** It produces an RGBA array + bounds; the result is a plain
  `Image`, so *every* backend renders a datashaded element for free. The routing
  (Scatter/Curve → Image) lives in the pipeline, not in any backend.
- **Out-of-core.** `channel_frame` keeps a dask source **lazy** — it assigns the
  channel accessors as columns on the dask frame and hands that to datashader,
  which aggregates partition-by-partition. Only the small raster is materialized.

Coverage (D22):
- **glyph** — `points` (Scatter) and `line` (Curve).
- **aggregation** — density (`count`) by default; when an element carries
  `color_by`, a *numeric* column aggregates as `mean` (continuous, shaded with a
  colormap) and a *categorical* column aggregates as `by(count)` (per-category
  blend, shaded with a color key).

This module is the aggregation primitive; the viewport-driven re-aggregation loop
lives in `core/raster.py` (4b) and calls `rasterize_element` here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.palette import _CATEGORY10, _VIRIDIS
from ..data.accessor import resolve_expr

_FRAME_MODULES = ("dask.dataframe", "dask_expr", "pandas")
_DASK_MODULES = ("dask.dataframe", "dask_expr")


# ── reverse-lookup value objects ([D46], milestone-raster-inspect.md) ──────────
@dataclass(frozen=True)
class RasterAggregate:
    """The pre-shade per-pixel aggregate behind a datashaded raster, plus the
    data-space extent — enough to map a cursor coord back to its value. Pure
    (numpy only), so hover/inspect logic is Tier-1 testable with no Qt."""

    values: np.ndarray  # (rows=y, cols=x) scalar agg; row 0 == ymin (origin lower-left)
    bounds: tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
    kind: str  # "count" | "mean" | "category" — what the value means

    def value_at(self, x: float, y: float) -> float | None:
        """Data coords → pixel → value. `None` outside `bounds` or on an empty
        pixel (NaN, or count/category == 0)."""
        xmin, ymin, xmax, ymax = self.bounds
        if xmax <= xmin or ymax <= ymin:
            return None
        if not (xmin <= x <= xmax and ymin <= y <= ymax):
            return None
        h, w = self.values.shape[:2]
        col = min(int((x - xmin) / (xmax - xmin) * w), w - 1)
        row = min(int((y - ymin) / (ymax - ymin) * h), h - 1)
        v = float(self.values[row, col])
        if np.isnan(v):
            return None
        if self.kind in ("count", "category") and v == 0.0:
            return None
        return v


@dataclass(frozen=True)
class RasterResult:
    """A rasterizer's full output: the RGBA image, its data-space bounds, and the
    aggregate the image was shaded from (for reverse-lookup / inspect)."""

    rgba: np.ndarray
    bounds: tuple[float, float, float, float]
    aggregate: RasterAggregate


def channel_frame(ref, channels: dict):
    """Build a dataframe whose columns are the resolved channels. A dask source
    stays a (lazy) dask frame so datashader aggregates it out-of-core; anything
    else falls back to an eager pandas frame. Column dtypes are preserved, so a
    categorical `color_by` column stays categorical."""
    native = ref.native()
    if type(native).__module__.startswith(_FRAME_MODULES):
        cols = {role: resolve_expr(a, columns=native, native=native)
                for role, a in channels.items()}
        return native.assign(**cols)[list(channels)]
    import pandas as pd  # noqa: PLC0415

    return pd.DataFrame(ref.resolve_channels(channels))


# ── core: aggregate + shade ──────────────────────────────────────────────────
def _aggregate_and_shade(
    frame, glyph: str, x: str, y: str, *,
    width: int, height: int, x_range, y_range,
    color_by, cmap, color_key, how: str,
):
    import datashader as ds  # noqa: PLC0415
    import datashader.transfer_functions as tf  # noqa: PLC0415

    canvas = ds.Canvas(plot_width=width, plot_height=height, x_range=x_range, y_range=y_range)
    glyph_fn = canvas.line if glyph == "line" else canvas.points

    if color_by is None:  # density
        agg = glyph_fn(frame, x, y, agg=ds.count())
        img = tf.shade(agg, cmap=list(cmap) if cmap else list(_VIRIDIS), how=how)
        values, kind = np.asarray(agg.values, dtype=float), "count"
    elif _is_categorical(frame[color_by]):  # per-category blend
        frame = _categorize(frame, color_by)
        agg = glyph_fn(frame, x, y, agg=ds.by(color_by, ds.count()))
        key = color_key or _color_key(_categories(frame, color_by))
        img = tf.shade(agg, color_key=key, how=how)
        # categorical agg is (y, x, cat); collapse to total count per pixel
        values, kind = np.asarray(agg.values, dtype=float).sum(axis=-1), "category"
    else:  # continuous value
        agg = glyph_fn(frame, x, y, agg=ds.mean(color_by))
        img = tf.shade(agg, cmap=list(cmap) if cmap else list(_VIRIDIS), how=how)
        values, kind = np.asarray(agg.values, dtype=float), "mean"

    rgba = img.data.view(np.uint8).reshape(img.shape + (4,)).copy()  # (y, x, 4)
    xs = np.asarray(agg.coords[x].values)
    ys = np.asarray(agg.coords[y].values)
    bounds = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
    return RasterResult(rgba, bounds, RasterAggregate(values, bounds, kind))


def rasterize_points(
    frame, x: str, y: str, *,
    width: int, height: int, x_range=None, y_range=None,
    color_by: str | None = None, cmap=None, color_key=None, how: str = "eq_hist",
) -> RasterResult:
    """Aggregate point density (or `color_by` value/category) into an RGBA raster.
    Returns a `RasterResult` — `rgba` is `(rows=y, cols=x, 4)` uint8 (origin
    lower-left), `bounds` is `(xmin, ymin, xmax, ymax)`, `aggregate` is the
    pre-shade per-pixel values for reverse-lookup ([D46])."""
    return _aggregate_and_shade(
        frame, "points", x, y, width=width, height=height, x_range=x_range, y_range=y_range,
        color_by=color_by, cmap=cmap, color_key=color_key, how=how,
    )


def rasterize_line(
    frame, x: str, y: str, *,
    width: int, height: int, x_range=None, y_range=None,
    cmap=None, how: str = "eq_hist",
) -> RasterResult:
    """Aggregate connected line segments (a Curve) into an RGBA raster — the
    density of overlapping lines, for huge/dense series."""
    return _aggregate_and_shade(
        frame, "line", x, y, width=width, height=height, x_range=x_range, y_range=y_range,
        color_by=None, cmap=cmap, color_key=None, how=how,
    )


# ── element adapters ─────────────────────────────────────────────────────────
def rasterize_scatter(element, *, width: int, height: int, x_range=None, y_range=None):
    """Rasterize a Scatter's x/y (kept lazy for dask). `color_by` selects a value
    (numeric → mean) or category (→ per-category blend) aggregation."""
    color_by = getattr(element, "color_by", None)
    channels = {"x": element.x, "y": element.y}
    if color_by is not None:
        channels["color_by"] = color_by
    frame = channel_frame(element.data, channels)
    return rasterize_points(
        frame, "x", "y", width=width, height=height, x_range=x_range, y_range=y_range,
        color_by="color_by" if color_by is not None else None,
    )


def rasterize_curve(element, *, width: int, height: int, x_range=None, y_range=None):
    """Rasterize a Curve as a line-density raster (kept lazy for dask)."""
    frame = channel_frame(element.data, {"x": element.x, "y": element.y})
    return rasterize_line(
        frame, "x", "y", width=width, height=height, x_range=x_range, y_range=y_range,
    )


def rasterize_element(element, *, width: int, height: int, x_range=None, y_range=None):
    """Dispatch a rasterizable element to its glyph. Used by the pipeline routing
    and the dynamic re-aggregation controller, so both cover Scatter and Curve."""
    from ..elements import Curve  # noqa: PLC0415

    fn = rasterize_curve if isinstance(element, Curve) else rasterize_scatter
    return fn(element, width=width, height=height, x_range=x_range, y_range=y_range)


# ── categorical helpers ──────────────────────────────────────────────────────
def _is_categorical(series) -> bool:
    """True when a column should drive a per-category blend rather than a
    continuous mean — i.e. it is not a plain numeric/boolean dtype."""
    dtype = getattr(series, "dtype", None)
    if dtype is None:
        return np.asarray(series).dtype.kind not in "iufcb"
    kind = getattr(dtype, "kind", None)
    if kind is None:  # pandas extension dtype (category / string) → categorical
        return True
    return kind not in "iufcb"


def _categorize(frame, col: str):
    """Datashader's `by` needs a categorical dtype. dask must discover categories
    (a one-column scan); pandas casts in place."""
    if type(frame).__module__.startswith(_DASK_MODULES):
        return frame.categorize(columns=[col])
    return frame.assign(**{col: frame[col].astype("category")})


def _categories(frame, col: str) -> list:
    cat = getattr(frame[col], "cat", None)
    if cat is not None:
        return list(cat.categories)
    return sorted(set(np.asarray(frame[col]).tolist()))


def _color_key(categories: list, colors=_CATEGORY10) -> dict:
    return {c: colors[i % len(colors)] for i, c in enumerate(categories)}
