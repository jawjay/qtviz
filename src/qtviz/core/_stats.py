"""Shared statistics for the 0.4 vocabulary ([D67]–[D69], milestone-0.4).

Pure numpy, no Qt. One implementation per statistic so every backend draws the
*same* numbers — "one Element, one meaning" is never delegated to each engine's
house rules.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GRID_AGGS = ("mean", "sum", "count", "max", "min", "last")

# numpy's automatic bin-selection rules (np.histogram_bin_edges) — the string
# vocabulary `Histogram.bins` accepts besides an int ([D93]).
BIN_RULES = ("auto", "fd", "doane", "scott", "stone", "rice", "sturges", "sqrt")


def histogram(values, bins: int | str = "auto", *,
              density: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Shared histogram binning ([D93]) — one engine so every backend draws the
    *same* bars (previously np/mpl/Plotly each binned their own way). Returns
    `(counts, edges)` from `np.histogram` over the finite values."""
    a = np.asarray(values, dtype="float64")
    a = a[np.isfinite(a)]
    return np.histogram(a, bins=bins, density=density)


def contour_levels(values, levels) -> np.ndarray:
    """Shared contour level values ([D89]): an int becomes that many uniform
    *interior* levels across the finite data range; an explicit sequence passes
    through sorted — every backend draws the same lines."""
    if not isinstance(levels, int):
        return np.asarray(sorted(float(v) for v in levels), dtype="float64")
    a = np.asarray(values, dtype="float64")
    finite = a[np.isfinite(a)]
    lo, hi = float(finite.min()), float(finite.max())
    return np.linspace(lo, hi, levels + 2)[1:-1]


def ecdf(values) -> tuple[np.ndarray, np.ndarray]:
    """Empirical CDF ([D91]): the sorted finite sample points and the fraction
    of data ≤ each point. Drawn as a `post` step curve — one implementation so
    every backend draws the same staircase."""
    a = np.asarray(values, dtype="float64")
    a = np.sort(a[np.isfinite(a)])
    return a, np.arange(1, len(a) + 1, dtype="float64") / max(len(a), 1)


def cell_extent(centers) -> tuple[float, float]:
    """Outer edges spanned by a row of grid-cell centers (end cells extend half
    the adjacent spacing) — where an image drawn over those centers sits in
    data space ([D92])."""
    c = np.asarray(centers, dtype="float64")
    if len(c) == 1:
        return float(c[0]) - 0.5, float(c[0]) + 0.5
    return (float(c[0] - (c[1] - c[0]) / 2.0), float(c[-1] + (c[-1] - c[-2]) / 2.0))


@dataclass(frozen=True)
class BoxStats:
    """Five-number summary + outliers ([D67]): quartiles by linear interpolation
    (`np.percentile` default), whiskers at 1.5·IQR *clipped to the data*, and
    everything beyond the fences as outliers."""

    median: float
    q1: float
    q3: float
    lo_whisker: float
    hi_whisker: float
    outliers: np.ndarray


def box_stats(values) -> BoxStats:
    a = np.asarray(values, dtype="float64")
    a = a[np.isfinite(a)]
    q1, med, q3 = np.percentile(a, [25.0, 50.0, 75.0])
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = a[(a >= lo_fence) & (a <= hi_fence)]
    outliers = a[(a < lo_fence) | (a > hi_fence)]
    return BoxStats(float(med), float(q1), float(q3),
                    float(inside.min()), float(inside.max()), outliers)


def kde(values, n: int = 128) -> tuple[np.ndarray, np.ndarray]:
    """Gaussian kernel density on an `n`-point grid, Scott's-rule bandwidth
    ([D67]). Shared by every Violin renderer so no backend substitutes its own
    KDE. Returns `(grid, density)`; the density integrates to ~1."""
    a = np.asarray(values, dtype="float64")
    a = a[np.isfinite(a)]
    std = float(a.std(ddof=1)) if len(a) > 1 else 1.0
    bw = (std or 1.0) * len(a) ** (-1.0 / 5.0)
    grid = np.linspace(a.min() - 3.0 * bw, a.max() + 3.0 * bw, n)
    z = (grid[:, None] - a[None, :]) / bw
    density = np.exp(-0.5 * z * z).sum(axis=1) / (len(a) * bw * np.sqrt(2.0 * np.pi))
    return grid, density


def group_bars(x, y, groups) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Grouped/stacked bar data ([D68]): `(categories, group_names, matrix)` where
    `matrix[g, c]` is the summed `y` for group `g` at category `c` (missing
    combinations are 0). Categories and groups come out in `np.unique` order —
    the same canonical order `category_swatches` colors by."""
    xv = np.asarray(x)
    yv = np.asarray(y, dtype="float64")
    gv = np.asarray(groups)
    xs, x_codes = np.unique(xv, return_inverse=True)
    gs, g_codes = np.unique(gv, return_inverse=True)
    mat = np.zeros((len(gs), len(xs)))
    np.add.at(mat, (g_codes, x_codes), yv)
    return xs, gs, mat


def grid_reduce(xv, yv, zv, agg: str = "mean") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pivot tidy x/y/z onto a grid with a real reduction ([D69]) — closes the
    "last value wins" TODO (spec §5.5). Returns `(xs, ys, grid)` with empty cells
    NaN; `grid[j, i]` aggregates every row landing on `(xs[i], ys[j])`."""
    x = np.asarray(xv)
    y = np.asarray(yv)
    z = np.asarray(zv, dtype="float64")
    xs, x_codes = np.unique(x, return_inverse=True)
    ys, y_codes = np.unique(y, return_inverse=True)
    n = len(xs) * len(ys)
    flat = y_codes * len(xs) + x_codes
    counts = np.bincount(flat, minlength=n).astype("float64")
    filled = counts > 0
    grid = np.full(n, np.nan)
    if agg == "last":
        grid[flat] = z                                # assignment order = row order
    elif agg == "count":
        grid[filled] = counts[filled]
    elif agg in ("sum", "mean"):
        sums = np.bincount(flat, weights=z, minlength=n)
        grid[filled] = sums[filled] / (counts[filled] if agg == "mean" else 1.0)
    elif agg in ("max", "min"):
        op, init = (np.maximum, -np.inf) if agg == "max" else (np.minimum, np.inf)
        acc = np.full(n, init)
        op.at(acc, flat, z)
        grid[filled] = acc[filled]
    else:  # pragma: no cover - constructor validates
        raise ValueError(f"unknown aggregator {agg!r}")
    return xs, ys, grid.reshape(len(ys), len(xs))


def categorical_line_split(x, y, cats) -> tuple[np.ndarray, list]:
    """Split one polyline into per-category sub-lines ([D100]): segment
    i→i+1 belongs to `cats[i]`; each category keeps its segments' endpoints
    and NaNs elsewhere, so runs stay visually continuous and every backend
    draws the same split. Categories come out in `np.unique` order (the
    `category_swatches` rule)."""
    xa = np.asarray(x, dtype="float64")
    ya = np.asarray(y, dtype="float64")
    ca = np.asarray(cats)
    uniq = np.unique(ca)
    out = []
    for c in uniq:
        seg = ca[:-1] == c                     # segment i → i+1
        keep = np.zeros(len(xa), dtype=bool)
        keep[:-1] |= seg
        keep[1:] |= seg
        out.append((np.where(keep, xa, np.nan), np.where(keep, ya, np.nan)))
    return uniq, out


def split_by(values, by=None) -> tuple[np.ndarray | None, list[np.ndarray]]:
    """Split `values` into per-category arrays by the `by` column (np.unique
    order — the same canonical order `category_swatches` colors by), or one
    group when `by` is None."""
    v = np.asarray(values, dtype="float64")
    if by is None:
        return None, [v]
    b = np.asarray(by)
    cats, codes = np.unique(b, return_inverse=True)
    return cats, [v[codes == i] for i in range(len(cats))]
