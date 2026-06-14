"""matplotlib element renderers (spec §4.2).

Same Element vocabulary as pyqtgraph, drawn through `Axes`. Each returns the
mpl artist so interaction wiring can reach it.
"""

from __future__ import annotations

import numpy as np

from ...core.color import Color
from ...elements import (
    Bars,
    Curve,
    ErrorBars,
    Heatmap,
    Histogram,
    Image,
    Scatter,
    Spread,
)

_LINE_STYLE = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}


def _color(spec, theme, idx: int = 0) -> Color:
    if spec is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(spec)


def _col(ref, name) -> np.ndarray:
    return np.asarray(ref.series(name), dtype="float64")


def render_scatter(element: Scatter, ctx):
    size = (element.size or 6) ** 2  # mpl `s` is area; our size is ~diameter
    return ctx.parent_axes.scatter(
        _col(element.data, element.x), _col(element.data, element.y),
        color=_color(element.color, ctx.theme).mpl(), s=size, alpha=element.alpha,
    )


def render_curve(element: Curve, ctx):
    (line,) = ctx.parent_axes.plot(
        _col(element.data, element.x), _col(element.data, element.y),
        color=_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_LINE_STYLE[element.line_style], alpha=element.alpha,
    )
    return line


def render_bars(element: Bars, ctx):
    height = _col(element.data, element.y)
    try:
        x = _col(element.data, element.x)
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")
    return ctx.parent_axes.bar(x, height, color=_color(element.color, ctx.theme).mpl())


def render_histogram(element: Histogram, ctx):
    vals = _col(element.data, element.column)
    bins = element.bins if isinstance(element.bins, int) else "auto"
    _n, _bins, patches = ctx.parent_axes.hist(
        vals, bins=bins, density=element.density, color=_color(element.color, ctx.theme).mpl(),
    )
    return patches


def render_image(element: Image, ctx):
    x0, y0, x1, y1 = element.bounds
    return ctx.parent_axes.imshow(
        np.asarray(element.data.grid().values, dtype="float64"),
        extent=(x0, x1, y0, y1), origin="lower", aspect="auto", cmap=element.colormap,
    )


def render_heatmap(element: Heatmap, ctx):
    d = element.data
    xv, yv, zv = d.series(element.x), d.series(element.y), _col(d, element.z)
    xs, x_inv = np.unique(xv, return_inverse=True)
    ys, y_inv = np.unique(yv, return_inverse=True)
    grid = np.full((len(ys), len(xs)), np.nan)
    grid[y_inv, x_inv] = zv
    return ctx.parent_axes.imshow(grid, origin="lower", aspect="auto", cmap=element.colormap)


def render_errorbars(element: ErrorBars, ctx):
    d = element.data
    if isinstance(element.err, str):
        err = _col(d, element.err)
    else:
        err = np.vstack([_col(d, element.err[0]), _col(d, element.err[1])])
    kwargs = {"yerr": err} if element.direction in ("y", "both") else {"xerr": err}
    return ctx.parent_axes.errorbar(
        _col(d, element.x), _col(d, element.y), fmt="o",
        color=_color(element.color, ctx.theme).mpl(), **kwargs,
    )


def render_spread(element: Spread, ctx):
    d = element.data
    return ctx.parent_axes.fill_between(
        _col(d, element.x), _col(d, element.y_lo), _col(d, element.y_hi),
        color=_color(element.color, ctx.theme).mpl(), alpha=element.alpha,
    )


RENDERERS = {
    Scatter: render_scatter,
    Curve: render_curve,
    Bars: render_bars,
    Histogram: render_histogram,
    Image: render_image,
    Heatmap: render_heatmap,
    ErrorBars: render_errorbars,
    Spread: render_spread,
}
