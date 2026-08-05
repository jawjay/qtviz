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


# ── contour inline labels ([D117], wave 1.5) ─────────────────────────────────
def _cell_crossings(values, level):
    """Marching-squares segments of the `level` iso-line, in index coords
    (x=col, y=row). Returns a list of ((x0, y0), (x1, y1)) segments."""
    v = np.asarray(values, dtype="float64")
    above = v >= level
    ny, nx = v.shape
    # cells with at least one corner on each side of the level
    a00, a10 = above[:-1, :-1], above[:-1, 1:]
    a01, a11 = above[1:, :-1], above[1:, 1:]
    active = ~((a00 == a10) & (a00 == a01) & (a00 == a11))
    segs: list = []
    js, is_ = np.nonzero(active)
    for j, i in zip(js.tolist(), is_.tolist(), strict=True):
        v00, v10 = v[j, i], v[j, i + 1]
        v01, v11 = v[j + 1, i], v[j + 1, i + 1]
        if not np.isfinite([v00, v10, v01, v11]).all():
            continue
        pts = []  # crossing points on the four cell edges
        if (v00 >= level) != (v10 >= level):  # bottom
            pts.append((i + (level - v00) / (v10 - v00), float(j)))
        if (v10 >= level) != (v11 >= level):  # right
            pts.append((float(i + 1), j + (level - v10) / (v11 - v10)))
        if (v01 >= level) != (v11 >= level):  # top
            pts.append((i + (level - v01) / (v11 - v01), float(j + 1)))
        if (v00 >= level) != (v01 >= level):  # left
            pts.append((float(i), j + (level - v00) / (v01 - v00)))
        if len(pts) == 2:
            segs.append((pts[0], pts[1]))
        elif len(pts) == 4:  # saddle — resolve by the cell-center average
            center_above = (v00 + v10 + v01 + v11) / 4.0 >= level
            # pts order: bottom, right, top, left
            if (v00 >= level) == center_above:
                segs.append((pts[0], pts[3]))  # bottom–left, right–top
                segs.append((pts[1], pts[2]))
            else:
                segs.append((pts[0], pts[1]))  # bottom–right, left–top
                segs.append((pts[3], pts[2]))
    return segs


def iso_polylines(values, level) -> list[np.ndarray]:
    """The `level` iso-lines of a grid as chained polylines ([D117]) — a list
    of `(n, 2)` arrays in index coordinates (x=col, y=row), closed rings
    repeating their first point. Marching squares with the saddle resolved by
    the cell-center average; pure numpy + dict chaining."""
    segs = _cell_crossings(values, level)
    if not segs:
        return []

    def key(p):
        return (round(p[0] * 1e6), round(p[1] * 1e6))

    adj: dict = {}
    for si, (p, q) in enumerate(segs):
        adj.setdefault(key(p), []).append((si, 0))
        adj.setdefault(key(q), []).append((si, 1))
    used = [False] * len(segs)
    lines: list[np.ndarray] = []
    for start in range(len(segs)):
        if used[start]:
            continue
        used[start] = True
        path = [segs[start][0], segs[start][1]]
        for flip in (False, True):  # extend forward, then backward
            while True:
                end = path[-1] if not flip else path[0]
                nxt = None
                for si, side in adj.get(key(end), ()):
                    if not used[si]:
                        nxt = (si, side)
                        break
                if nxt is None:
                    break
                si, side = nxt
                used[si] = True
                other = segs[si][1 - side]
                if not flip:
                    path.append(other)
                else:
                    path.insert(0, other)
        lines.append(np.asarray(path, dtype="float64"))
    return lines


@dataclass(frozen=True)
class ContourLabel:
    """One inline contour label ([D117]): data-space position, CCW angle in
    (-90, 90] (never upside-down), the formatted text, the level's normalized
    position `t` in the drawn range (for line-matched coloring), and the
    background mask segment that breaks the line under the text."""

    x: float
    y: float
    angle: float
    text: str
    t: float
    mask: tuple[float, float, float, float]  # (x0, y0, x1, y1), data space


def contour_label_specs(values, levels, bounds, *, spec: str | bool = "auto",
                        char_frac: float = 0.016) -> list[ContourLabel]:
    """Core-placed inline labels ([D117]): per level, the longest iso-line's
    arc-length midpoint, angled along the local tangent. Computed once so
    every backend places identical labels ([D110] over engine fidelity — the
    recorded trade-off vs mpl's native `clabel`). The mask length estimates
    text width as `char_frac` of the larger span per character."""
    from ._ticks import format_tick  # noqa: PLC0415

    v = np.asarray(values, dtype="float64")
    lv = np.asarray(levels, dtype="float64")
    ny, nx = v.shape
    x0, y0, x1, y1 = (float(b) for b in bounds)
    sx = (x1 - x0) / max(nx - 1, 1)
    sy = (y1 - y0) / max(ny - 1, 1)
    lo, hi = float(lv[0]), float(lv[-1])
    span = (hi - lo) or 1.0
    out: list[ContourLabel] = []
    for level in lv:
        lines = iso_polylines(v, float(level))
        if not lines:
            continue  # the level doesn't cross the field — nothing to say
        pts = max(lines, key=lambda p: _arc_length(p, sx, sy))
        if len(pts) < 2:
            continue
        # data-space path + its arc-length midpoint
        data = np.column_stack([x0 + pts[:, 0] * sx, y0 + pts[:, 1] * sy])
        d = np.hypot(*np.diff(data, axis=0).T)
        cum = np.concatenate([[0.0], np.cumsum(d)])
        if cum[-1] == 0.0:
            continue
        k = int(np.searchsorted(cum, cum[-1] / 2.0))
        k = min(max(k, 1), len(data) - 1)
        px, py = (data[k - 1] + data[k]) / 2.0
        dx, dy = data[k] - data[k - 1]
        angle = float(np.degrees(np.arctan2(dy, dx)))
        if angle > 90.0:
            angle -= 180.0
        elif angle <= -90.0:
            angle += 180.0
        text = (format_tick(float(level), spec) if isinstance(spec, str)
                and spec != "auto" else format(float(level), "g"))
        half = (len(text) + 1) * char_frac * max(x1 - x0, y1 - y0) / 2.0
        rad = np.deg2rad(angle)
        ca, sa = float(np.cos(rad)), float(np.sin(rad))
        out.append(ContourLabel(
            float(px), float(py), angle, text,
            (float(level) - lo) / span,
            (px - ca * half, py - sa * half, px + ca * half, py + sa * half)))
    return out


def _arc_length(pts: np.ndarray, sx: float, sy: float) -> float:
    d = np.diff(pts, axis=0)
    return float(np.hypot(d[:, 0] * sx, d[:, 1] * sy).sum())


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
        from ..errors import ValidationError  # noqa: PLC0415

        raise ValidationError(f"unknown aggregator {agg!r}")
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
