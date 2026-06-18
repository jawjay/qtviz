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

Shading is split from aggregation ([D47], roadmap §8.5): `aggregate_element`
produces a theme-free `Aggregate` (the raw datashader agg + bounds + the [D46]
hover view), and `shade_aggregate` turns that into a shaded `RasterResult`. The
split lets a backend shade with its `Theme`/`Palette` at render time (the theme
isn't in reach in the pipeline) and emit a legend, while the aggregation stays
out-of-core and theme-free. `rasterize_*` keep aggregate+default-shade in one call
for back-compatible callers (the pipeline placeholder, the 4b controller).

This module is the aggregation primitive; the viewport-driven re-aggregation loop
lives in `core/raster.py` (4b) and calls `rasterize_element` / `aggregate_element`
here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ..core.color import Color
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
class Aggregate:
    """The theme-free output of the aggregation step ([D47]): the raw datashader
    `agg` (an xarray `DataArray` — `(y, x)` for count/value, `(y, x, cat)` for a
    categorical blend), its data-space `bounds`, the `kind`/agg name, and the
    ordered `categories` for a categorical blend (else `None`). Carries the
    pure-numpy `RasterAggregate` so [D46] hover keeps working unchanged.

    Shading is deliberately *not* applied here: `shade_aggregate` turns this into a
    `RasterResult` at render time, where the `Theme`/`Palette` is in reach. Keeping
    the raw `agg` lets that shade step re-run `tf.shade` faithfully (no numpy
    re-implementation of `eq_hist`/categorical blend)."""

    agg: object  # xarray DataArray; theme-free, the raw per-pixel aggregation
    bounds: tuple[float, float, float, float]
    kind: str  # "count" | "mean" | "category" (widens with the agg surface, C4)
    categories: tuple | None  # categorical blend: ordered labels; else None
    aggregate: RasterAggregate  # pure-numpy hover view ([D46])


@dataclass(frozen=True)
class RasterResult:
    """A rasterizer's full output: the RGBA image, its data-space bounds, the
    aggregate the image was shaded from (for reverse-lookup / inspect), and the
    `Legend` describing the color↔value mapping (None until shaded with a palette;
    C3). Backends draw the legend via the same path as a native `color_by`."""

    rgba: np.ndarray
    bounds: tuple[float, float, float, float]
    aggregate: RasterAggregate
    legend: object | None = None  # core.encoding.Legend | None


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


# ── step 1: aggregate (theme-free) ───────────────────────────────────────────
def _aggregate(
    frame, glyph: str, x: str, y: str, *,
    width: int, height: int, x_range, y_range, color_by, agg: str = "auto",
) -> Aggregate:
    """Run the datashader Canvas aggregation and return a theme-free `Aggregate`.
    The reduction (`agg`, [D49]) is an *aggregation* concern — it shapes the agg — so
    it is chosen here; the palette/cmap is a *shading* concern, deferred to
    `shade_aggregate`."""
    import datashader as ds  # noqa: PLC0415

    canvas = ds.Canvas(plot_width=width, plot_height=height, x_range=x_range, y_range=y_range)
    glyph_fn = canvas.line if glyph == "line" else canvas.points

    categories = None
    if _is_category_agg(agg, color_by, frame):  # per-category blend
        frame = _categorize(frame, color_by)
        categories = tuple(_categories(frame, color_by))
        agg_arr = glyph_fn(frame, x, y, agg=ds.by(color_by, ds.count()))
        # categorical agg is (y, x, cat); collapse to total count per pixel
        values, kind = np.asarray(agg_arr.values, dtype=float).sum(axis=-1), "category"
    else:
        reducer, kind = _reducer(ds, agg, color_by)
        agg_arr = glyph_fn(frame, x, y, agg=reducer)
        values = np.asarray(agg_arr.values, dtype=float)

    xs = np.asarray(agg_arr.coords[x].values)
    ys = np.asarray(agg_arr.coords[y].values)
    bounds = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
    return Aggregate(agg_arr, bounds, kind, categories, RasterAggregate(values, bounds, kind))


def _is_category_agg(agg: str, color_by, frame) -> bool:
    """A per-category blend: an explicit `agg="by"`, or `agg="auto"` over a
    categorical `color_by` column (the default for a categorical value)."""
    if color_by is None:
        return False
    if agg == "by":
        return True
    return agg == "auto" and _is_categorical(frame[color_by])


def _reducer(ds, agg: str, color_by):
    """Map an `agg` spec to a datashader reduction + the kind it produces. `auto` is
    the back-compatible default (count with no `color_by`, else mean)."""
    if agg in ("auto", "mean"):
        return (ds.count(), "count") if (agg == "auto" and color_by is None) \
            else (ds.mean(color_by), "mean")
    if agg == "count":
        return ds.count(), "count"
    if agg == "any":
        return ds.any(), "count"
    reducer = {"sum": ds.sum, "max": ds.max, "min": ds.min, "std": ds.std}[agg]
    return reducer(color_by), agg


# Value aggregations whose colorbar is a *linear* value scale (so default `how` is
# linear and the legend shows interior ticks); `count` density stays non-linear
# eq_hist with an endpoints-only legend ([D48]).
_VALUE_KINDS = frozenset({"mean", "sum", "max", "min", "std"})


# ── step 2: shade (theme-aware) ──────────────────────────────────────────────
def shade_aggregate(
    aggregate: Aggregate, *,
    palette=None, continuous_palette=None, cmap=None, color_key=None,
    how: str | None = None, title: str | None = None,
) -> RasterResult:
    """Shade a theme-free `Aggregate` into a `RasterResult` ([D47]) and build its
    `Legend` (C3). The categorical blend takes its key from `palette` (a
    `Theme.palette`); `count`/value aggregations take their ramp from
    `continuous_palette`. An explicit datashader `color_key`/`cmap` wins over the
    palette; with nothing supplied it falls back to the vendored `category10`/
    `viridis`, so non-themed callers (and the pipeline placeholder shade) are
    unchanged. Category→color uses `core.encoding`'s shared `category_swatches`, so a
    raster matches a native categorical `Scatter` ([D50]).

    `how` defaults per [D48]: a *value* aggregation (`mean`/`sum`/…) shades linearly
    so its colorbar is truthful; `count` density keeps `eq_hist` (best visual) with a
    non-linear, endpoints-only legend."""
    import datashader.transfer_functions as tf  # noqa: PLC0415

    how = how or ("linear" if aggregate.kind in _VALUE_KINDS else "eq_hist")
    if aggregate.kind == "category":
        key = color_key or _theme_color_key(list(aggregate.categories or ()), palette)
        img = tf.shade(aggregate.agg, color_key=key, how=how)
    else:
        ramp = cmap or _palette_cmap(continuous_palette)
        img = tf.shade(aggregate.agg, cmap=list(ramp), how=how)
    rgba = img.data.view(np.uint8).reshape(img.shape + (4,)).copy()  # (y, x, 4)
    legend = _raster_legend(aggregate, palette=palette, continuous_palette=continuous_palette,
                            color_key=color_key, title=title)
    return RasterResult(rgba, aggregate.bounds, aggregate.aggregate, legend)


def _raster_legend(aggregate: Aggregate, *, palette, continuous_palette, color_key, title):
    """Build the `core.encoding.Legend` for a shaded raster (C3). Categorical → a
    category key; a value aggregation → a linear colorbar with true `vmin`/`vmax`;
    `count` density → a non-linear ramp keyed at its endpoints only ([D48])."""
    from ..core.encoding import Legend, category_swatches, continuous_ramp  # noqa: PLC0415
    from ..core.palette import palettes  # noqa: PLC0415

    if aggregate.kind == "category":
        cats = list(aggregate.categories or ())
        swatches = (category_swatches(cats, palette) if palette is not None
                    else [Color(color_key[c]) for c in cats] if color_key
                    else [Color(_CATEGORY10[i % len(_CATEGORY10)]) for i in range(len(cats))])
        entries = tuple((str(c), sw) for c, sw in zip(cats, swatches, strict=True))
        return Legend(kind="categorical", title=title, entries=entries)

    ramp = continuous_ramp(continuous_palette if continuous_palette is not None
                           else palettes.get("viridis"))
    vmin, vmax = _value_range(aggregate.aggregate.values)
    default_title = "density" if aggregate.kind == "count" else None
    return Legend(kind="continuous", title=title or default_title,
                  vmin=vmin, vmax=vmax, ramp=ramp, linear=aggregate.kind in _VALUE_KINDS)


def _value_range(values) -> tuple[float, float]:
    """Min/max over the finite pixels — empty `mean` pixels are NaN (skipped);
    empty `count` pixels are 0, so a density range starts at 0."""
    arr = np.asarray(values, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return 0.0, 1.0
    return float(finite.min()), float(finite.max())


def _theme_color_key(categories: list, palette) -> dict:
    """Category → datashader color (hex). From the `Theme.palette` when given (via
    the shared `category_swatches`), else the vendored `category10` default."""
    if palette is None:
        return _color_key(categories)
    from ..core.encoding import category_swatches  # noqa: PLC0415

    swatches = category_swatches(categories, palette)
    return {cat: sw.hex() for cat, sw in zip(categories, swatches, strict=True)}


def _palette_cmap(palette) -> list:
    """Continuous ramp as hex stops for `tf.shade(cmap=...)`. The `Theme`'s
    continuous palette when given, else the vendored viridis."""
    if palette is None:
        return list(_VIRIDIS)
    return [c.hex() for c in palette]


def rasterize_points(
    frame, x: str, y: str, *,
    width: int, height: int, x_range=None, y_range=None,
    color_by: str | None = None, cmap=None, color_key=None, how: str = "eq_hist",
) -> RasterResult:
    """Aggregate point density (or `color_by` value/category) into an RGBA raster.
    Returns a `RasterResult` — `rgba` is `(rows=y, cols=x, 4)` uint8 (origin
    lower-left), `bounds` is `(xmin, ymin, xmax, ymax)`, `aggregate` is the
    pre-shade per-pixel values for reverse-lookup ([D46])."""
    agg = _aggregate(frame, "points", x, y, width=width, height=height,
                     x_range=x_range, y_range=y_range, color_by=color_by)
    return shade_aggregate(agg, cmap=cmap, color_key=color_key, how=how)


def rasterize_line(
    frame, x: str, y: str, *,
    width: int, height: int, x_range=None, y_range=None,
    cmap=None, how: str = "eq_hist",
) -> RasterResult:
    """Aggregate connected line segments (a Curve) into an RGBA raster — the
    density of overlapping lines, for huge/dense series."""
    agg = _aggregate(frame, "line", x, y, width=width, height=height,
                     x_range=x_range, y_range=y_range, color_by=None)
    return shade_aggregate(agg, cmap=cmap, how=how)


# ── element adapters: aggregate (theme-free) ─────────────────────────────────
def _aggregate_scatter(element, *, width, height, x_range, y_range) -> Aggregate:
    color_by = getattr(element, "color_by", None)
    channels = {"x": element.x, "y": element.y}
    if color_by is not None:
        channels["color_by"] = color_by
    frame = channel_frame(element.data, channels)
    return _aggregate(
        frame, "points", "x", "y", width=width, height=height,
        x_range=x_range, y_range=y_range,
        color_by="color_by" if color_by is not None else None,
        agg=getattr(element, "agg", "auto"),
    )


def _aggregate_curve(element, *, width, height, x_range, y_range) -> Aggregate:
    frame = channel_frame(element.data, {"x": element.x, "y": element.y})
    return _aggregate(
        frame, "line", "x", "y", width=width, height=height,
        x_range=x_range, y_range=y_range, color_by=None,
    )


def aggregate_element(element, *, width: int, height: int, x_range=None, y_range=None) -> Aggregate:
    """Dispatch a rasterizable element to its glyph and aggregate it (theme-free).
    The shade step (`shade_aggregate`) is applied separately at render time, where
    the `Theme` is in reach ([D47])."""
    from ..elements import Curve  # noqa: PLC0415

    fn = _aggregate_curve if isinstance(element, Curve) else _aggregate_scatter
    return fn(element, width=width, height=height, x_range=x_range, y_range=y_range)


def themed_rasterize(palette=None, continuous_palette=None, title=None) -> Callable:
    """A `rasterize` callable for the 4b `RasterController` that aggregates the
    source (theme-free, off-thread) and shades it with the given `Theme` palettes,
    carrying the legend title across re-aggregations. The theme is closed over here,
    so `core.raster` stays palette-free ([D47]) — the backend injects this in place
    of the bare `rasterize_element`."""

    def _rasterize(source, *, width, height, x_range=None, y_range=None):
        agg = aggregate_element(source, width=width, height=height,
                                x_range=x_range, y_range=y_range)
        return shade_aggregate(agg, palette=palette, continuous_palette=continuous_palette,
                               title=title)

    return _rasterize


# ── element adapters: aggregate + default shade (back-compatible) ────────────
def rasterize_scatter(element, *, width: int, height: int, x_range=None, y_range=None):
    """Rasterize a Scatter's x/y (kept lazy for dask). `color_by` selects a value
    (numeric → mean) or category (→ per-category blend) aggregation. Shaded with
    the default palette — a backend re-shades with its `Theme` (C2)."""
    return shade_aggregate(
        _aggregate_scatter(element, width=width, height=height, x_range=x_range, y_range=y_range)
    )


def rasterize_curve(element, *, width: int, height: int, x_range=None, y_range=None):
    """Rasterize a Curve as a line-density raster (kept lazy for dask)."""
    return shade_aggregate(
        _aggregate_curve(element, width=width, height=height, x_range=x_range, y_range=y_range)
    )


def rasterize_element(element, *, width: int, height: int, x_range=None, y_range=None):
    """Dispatch a rasterizable element to its glyph + default shade. Used by the
    pipeline routing and the dynamic re-aggregation controller, so both cover
    Scatter and Curve."""
    return shade_aggregate(
        aggregate_element(element, width=width, height=height, x_range=x_range, y_range=y_range)
    )


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
