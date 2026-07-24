"""Shared statistics for the 0.4 vocabulary ([D67]–[D69], milestone-0.4).

Pure numpy, no Qt. One implementation per statistic so every backend draws the
*same* numbers — "one Element, one meaning" is never delegated to each engine's
house rules.
"""

from __future__ import annotations

import numpy as np

GRID_AGGS = ("mean", "sum", "count", "max", "min", "last")


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
