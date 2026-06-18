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


def _u8(rgba_row) -> tuple[int, int, int, int]:
    return tuple(int(round(v * 255)) for v in rgba_row)


def _scaled_sizes(values, lo: float = 5.0, hi: float = 18.0):
    a = np.asarray(values, dtype="float64")
    vmin, vmax = float(np.nanmin(a)), float(np.nanmax(a))
    span = (vmax - vmin) or 1.0
    return lo + (a - vmin) / span * (hi - lo)


def _color_mapping(element, d, theme):
    from ...core.encoding import map_colors  # noqa: PLC0415
    from ...core.palette import palettes  # noqa: PLC0415

    return map_colors(
        np.asarray(d.series("color")), palette=theme.palette,
        continuous_palette=palettes.get("viridis"), title=element.color_by,
    )


def render_scatter(element: Scatter, ctx):
    d = element.data
    kwargs = {"pen": None, "useCache": True, "hoverable": True}
    kwargs["size"] = (
        _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6)
    )
    legend = None
    if element.color_by is not None:
        rgba, legend = _color_mapping(element, d, ctx.theme)
        kwargs["brush"] = [pg.mkBrush(*_u8(c)) for c in rgba]
    else:
        kwargs["brush"] = pg.mkBrush(_color(element.color, ctx.theme).qt())
    item = pg.ScatterPlotItem(x=_col(d, "x"), y=_col(d, "y"), **kwargs)
    ctx.parent_axes.addItem(item)
    if legend is not None:
        from ._legend import add_legend  # noqa: PLC0415

        add_legend(ctx.parent_axes, legend, ctx.theme)
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

    agg = getattr(element, "_raster_agg", None)
    if agg is not None:  # datashaded raster: shade + legend with the View's Theme (C2/C3)
        result = _shade_raster(element, agg, ctx.theme)
        item = pg.ImageItem(result.rgba, axisOrder="row-major")
    else:
        result = None
        values = np.asarray(element.data.grid().values)
        if values.ndim == 3:  # RGBA raster (e.g. a user-built image): row 0 = ymin
            item = pg.ImageItem(values, axisOrder="row-major")
        else:
            item = pg.ImageItem(np.asarray(values, dtype="float64"))
    x0, y0, x1, y1 = element.bounds
    item.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    ctx.parent_axes.addItem(item)
    if result is not None and result.legend is not None:
        from ._legend import add_legend  # noqa: PLC0415

        add_legend(ctx.parent_axes, result.legend, ctx.theme)  # category key / colorbar (C3)
    _wire_dynamic_raster(element, item, ctx)
    return item


def _shade_raster(element, aggregate, theme):
    """Shade a datashader `Aggregate` with the View's `Theme` into rgba + a `Legend`
    (categorical key from `theme.palette`, continuous ramp from viridis), so a raster
    matches a native `color_by` (C2/C3, [D50])."""
    from ...core.palette import palettes  # noqa: PLC0415
    from ...ext.datashader import shade_aggregate  # noqa: PLC0415

    return shade_aggregate(
        aggregate, palette=theme.palette, continuous_palette=palettes.get("viridis"),
        title=_raster_title(element),
    )


def _raster_title(element) -> str | None:
    """Legend title for a datashaded raster — the source's `color_by` column, or
    `None` (→ `shade_aggregate` labels a bare density `count` as "density")."""
    return getattr(getattr(element, "_raster_source", None), "color_by", None)


def _wire_dynamic_raster(element, item, ctx) -> None:
    """If this Image came from a datashaded Scatter/Curve, attach a controller that
    re-aggregates the source to the viewport on pan/zoom (4b) and a hover handler
    that reports the aggregated value under the cursor ([D46]). Both are parked on
    the ViewBox so the RenderHandle disposes them (Disposable + controller both
    expose `.dispose()`)."""
    source = getattr(element, "_raster_source", None)
    if source is None:
        return
    from types import SimpleNamespace  # noqa: PLC0415

    from ...core.palette import palettes  # noqa: PLC0415
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...ext.datashader import themed_rasterize  # noqa: PLC0415
    from ._legend import add_legend  # noqa: PLC0415
    from ._raster import PgRasterTarget, wire_raster_hover  # noqa: PLC0415

    vb = ctx.parent_axes.getViewBox()
    plot = ctx.parent_axes
    theme = ctx.theme
    holder = SimpleNamespace(aggregate=getattr(element, "_raster_aggregate", None))
    target = PgRasterTarget(item, vb)
    controller = RasterController(
        source=source, target=target,
        rasterize=themed_rasterize(theme.palette, palettes.get("viridis"), _raster_title(element)),
        parent=vb, on_aggregate=lambda agg: setattr(holder, "aggregate", agg),
        on_legend=lambda lg: add_legend(plot, lg, theme),  # refresh on re-aggregation (C3)
    )
    if not hasattr(vb, "_qtviz_rasters"):
        vb._qtviz_rasters = []
    vb._qtviz_rasters.append(controller)
    vb._qtviz_rasters.append(wire_raster_hover(vb, element.id, ctx.event_bus, holder))


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
