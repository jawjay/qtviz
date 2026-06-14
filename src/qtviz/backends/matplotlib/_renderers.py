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


def _scaled_sizes(values, lo: float = 5.0, hi: float = 18.0):
    a = np.asarray(values, dtype="float64")
    vmin, vmax = float(np.nanmin(a)), float(np.nanmax(a))
    span = (vmax - vmin) or 1.0
    return (lo + (a - vmin) / span * (hi - lo)) ** 2  # mpl `s` is area


def _color_mapping(element, d, theme):
    from ...core.encoding import map_colors  # noqa: PLC0415
    from ...core.palette import palettes  # noqa: PLC0415

    return map_colors(
        np.asarray(d.series("color")), palette=theme.palette,
        continuous_palette=palettes.get("viridis"), title=element.color_by,
    )


def render_scatter(element: Scatter, ctx):
    d = element.data
    s = _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6) ** 2
    if element.color_by is not None:
        rgba, legend = _color_mapping(element, d, ctx.theme)
        artist = ctx.parent_axes.scatter(
            _col(d, "x"), _col(d, "y"), c=rgba, s=s, alpha=element.alpha,
        )
        _add_legend(ctx.parent_axes, legend, ctx.theme)
        return artist
    return ctx.parent_axes.scatter(
        _col(d, "x"), _col(d, "y"),
        color=_color(element.color, ctx.theme).mpl(), s=s, alpha=element.alpha,
    )


def _add_legend(ax, legend, theme) -> None:
    fg = theme.foreground.mpl()
    if legend.kind == "categorical":
        from matplotlib.patches import Patch  # noqa: PLC0415

        handles = [Patch(facecolor=c.mpl(), label=label) for label, c in legend.entries]
        ax.legend(handles=handles, title=legend.title, fontsize=8, framealpha=0.85, labelcolor=fg)
    else:
        from matplotlib.cm import ScalarMappable  # noqa: PLC0415
        from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: PLC0415

        cmap = LinearSegmentedColormap.from_list("qtviz", [c.mpl() for c in legend.ramp])
        sm = ScalarMappable(norm=Normalize(legend.vmin, legend.vmax), cmap=cmap)
        bar = ax.figure.colorbar(sm, ax=ax)
        if legend.title:
            bar.set_label(legend.title, color=fg)
        bar.ax.tick_params(colors=fg)


def render_curve(element: Curve, ctx):
    (line,) = ctx.parent_axes.plot(
        _col(element.data, "x"), _col(element.data, "y"),
        color=_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_LINE_STYLE[element.line_style], alpha=element.alpha,
    )
    return line


def render_bars(element: Bars, ctx):
    height = _col(element.data, "y")
    try:
        x = _col(element.data, "x")
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")
    return ctx.parent_axes.bar(x, height, color=_color(element.color, ctx.theme).mpl())


def render_histogram(element: Histogram, ctx):
    vals = _col(element.data, "column")
    bins = element.bins if isinstance(element.bins, int) else "auto"
    _n, _bins, patches = ctx.parent_axes.hist(
        vals, bins=bins, density=element.density, color=_color(element.color, ctx.theme).mpl(),
    )
    return patches


def render_image(element: Image, ctx):
    x0, y0, x1, y1 = element.bounds
    values = np.asarray(element.data.grid().values)
    if values.ndim == 3:  # RGBA raster (e.g. datashaded scatter)
        artist = ctx.parent_axes.imshow(
            values, extent=(x0, x1, y0, y1), origin="lower", aspect="auto"
        )
        _wire_dynamic_raster(element, artist, ctx)
        return artist
    return ctx.parent_axes.imshow(
        np.asarray(values, dtype="float64"),
        extent=(x0, x1, y0, y1), origin="lower", aspect="auto", cmap=element.colormap,
    )


def _wire_dynamic_raster(element, artist, ctx) -> None:
    """If this Image came from a datashaded Scatter, re-aggregate the source to
    the viewport on pan/zoom (4b). Controllers are parked on the Axes so the
    RenderHandle can dispose them."""
    source = getattr(element, "_raster_source", None)
    if source is None:
        return
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...ext.datashader import rasterize_element  # noqa: PLC0415
    from ._raster import MplRasterTarget  # noqa: PLC0415

    ax = ctx.parent_axes
    target = MplRasterTarget(artist, ax)
    controller = RasterController(
        source=source, target=target, rasterize=rasterize_element, parent=ax.figure.canvas
    )
    if not hasattr(ax, "_qtviz_rasters"):
        ax._qtviz_rasters = []
    ax._qtviz_rasters.append(controller)


def render_heatmap(element: Heatmap, ctx):
    d = element.data
    xv, yv, zv = d.series("x"), d.series("y"), _col(d, "z")
    xs, x_inv = np.unique(xv, return_inverse=True)
    ys, y_inv = np.unique(yv, return_inverse=True)
    grid = np.full((len(ys), len(xs)), np.nan)
    grid[y_inv, x_inv] = zv
    return ctx.parent_axes.imshow(grid, origin="lower", aspect="auto", cmap=element.colormap)


def render_errorbars(element: ErrorBars, ctx):
    d = element.data
    lo, hi = _col(d, "err_lo"), _col(d, "err_hi")
    err = np.vstack([lo, hi])  # [below, above]
    kwargs = {"yerr": err} if element.direction in ("y", "both") else {"xerr": err}
    return ctx.parent_axes.errorbar(
        _col(d, "x"), _col(d, "y"), fmt="o",
        color=_color(element.color, ctx.theme).mpl(), **kwargs,
    )


def render_spread(element: Spread, ctx):
    d = element.data
    return ctx.parent_axes.fill_between(
        _col(d, "x"), _col(d, "y_lo"), _col(d, "y_hi"),
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
