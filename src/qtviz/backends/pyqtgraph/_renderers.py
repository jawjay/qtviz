"""pyqtgraph element renderers (spec §4.1).

One function per Element type. By the time a renderer runs, the resolve pipeline
(D14) has replaced the Element's data with a role-keyed eager ref, so renderers
read channels by their fixed **role** name (`"x"`, `"y"`, …) — never the user's
accessor, which may be a string, Expression, callable, or array.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg

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


def _color(spec, theme, idx: int = 0) -> Color:
    if spec is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(spec)


def _col(ref, name) -> np.ndarray:
    return np.asarray(ref.series(name), dtype="float64")


def render_scatter(element: Scatter, ctx):
    d = element.data
    item = pg.ScatterPlotItem(
        x=_col(d, "x"),
        y=_col(d, "y"),
        brush=pg.mkBrush(_color(element.color, ctx.theme).qt()),
        pen=None,
        size=element.size or 6,
        useCache=True,
        hoverable=True,
    )
    ctx.parent_axes.addItem(item)
    return item


def render_curve(element: Curve, ctx):
    d = element.data
    pen = pg.mkPen(_color(element.color, ctx.theme).qt(), width=element.line_width)
    item = pg.PlotCurveItem(x=_col(d, "x"), y=_col(d, "y"), pen=pen)
    ctx.parent_axes.addItem(item)
    return item


def render_bars(element: Bars, ctx):
    d = element.data
    height = _col(d, "y")
    try:
        x = _col(d, "x")
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")  # categorical → indices
    brush = _color(element.color, ctx.theme).qt()
    item = pg.BarGraphItem(x=x, height=height, width=0.6, brush=brush)
    ctx.parent_axes.addItem(item)
    return item


def render_histogram(element: Histogram, ctx):
    vals = _col(element.data, "column")
    bins = element.bins if isinstance(element.bins, int) else "auto"
    counts, edges = np.histogram(vals, bins=bins, density=element.density)
    centers = (edges[:-1] + edges[1:]) / 2.0
    width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0
    item = pg.BarGraphItem(x=centers, height=counts, width=width * 0.95,
                           brush=_color(element.color, ctx.theme).qt())
    ctx.parent_axes.addItem(item)
    return item


def render_image(element: Image, ctx):
    from PySide6.QtCore import QRectF  # noqa: PLC0415

    values = np.asarray(element.data.grid().values)
    if values.ndim == 3:  # RGBA raster (e.g. datashaded scatter): row 0 = ymin
        item = pg.ImageItem(values, axisOrder="row-major")
    else:
        item = pg.ImageItem(np.asarray(values, dtype="float64"))
    x0, y0, x1, y1 = element.bounds
    item.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    ctx.parent_axes.addItem(item)
    _wire_dynamic_raster(element, item, ctx)
    return item


def _wire_dynamic_raster(element, item, ctx) -> None:
    """If this Image came from a datashaded Scatter, attach a controller that
    re-aggregates the source to the viewport on pan/zoom (4b). Controllers are
    parked on the ViewBox so the RenderHandle can dispose them."""
    source = getattr(element, "_raster_source", None)
    if source is None:
        return
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...ext.datashader import rasterize_scatter  # noqa: PLC0415
    from ._raster import PgRasterTarget  # noqa: PLC0415

    vb = ctx.parent_axes.getViewBox()
    target = PgRasterTarget(item, vb)
    controller = RasterController(
        source=source, target=target, rasterize=rasterize_scatter, parent=vb
    )
    if not hasattr(vb, "_qtviz_rasters"):
        vb._qtviz_rasters = []
    vb._qtviz_rasters.append(controller)


def render_heatmap(element: Heatmap, ctx):
    d = element.data
    xv, yv = d.series("x"), d.series("y")
    zv = _col(d, "z")
    xs, x_inv = np.unique(xv, return_inverse=True)
    ys, y_inv = np.unique(yv, return_inverse=True)
    grid = np.full((len(ys), len(xs)), np.nan)
    grid[y_inv, x_inv] = zv  # last value wins (aggregator TODO, §5.5)
    item = pg.ImageItem(grid)
    ctx.parent_axes.addItem(item)
    return item


def render_errorbars(element: ErrorBars, ctx):
    d = element.data
    item = pg.ErrorBarItem(
        x=_col(d, "x"), y=_col(d, "y"),
        top=_col(d, "err_hi"), bottom=_col(d, "err_lo"), beam=0.0,
    )
    ctx.parent_axes.addItem(item)
    return item


def render_spread(element: Spread, ctx):
    d = element.data
    x = _col(d, "x")
    lo = pg.PlotDataItem(x, _col(d, "y_lo"))
    hi = pg.PlotDataItem(x, _col(d, "y_hi"))
    brush = _color(element.color, ctx.theme).qt()
    brush.setAlphaF(element.alpha)
    fill = pg.FillBetweenItem(lo, hi, brush=brush)
    for it in (lo, hi, fill):
        ctx.parent_axes.addItem(it)
    return fill


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
