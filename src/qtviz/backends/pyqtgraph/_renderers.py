"""pyqtgraph element renderers (spec §4.1).

One function per Element type. By the time a renderer runs, the resolve pipeline
(D14) has replaced the Element's data with a role-keyed eager ref, so renderers
read channels by their fixed **role** name (`"x"`, `"y"`, …) — never the user's
accessor, which may be a string, Expression, callable, or array.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt

from ...core._scales import logify
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

# qtviz marker vocabulary → pyqtgraph symbol codes / Qt pen styles ([D51]).
_MARKER = {"circle": "o", "square": "s", "triangle": "t", "diamond": "d", "cross": "x"}
_PEN_STYLE = {
    "solid": Qt.SolidLine, "dashed": Qt.DashLine,
    "dotted": Qt.DotLine, "dashdot": Qt.DashDotLine,
}


def _color(spec, theme, idx: int = 0) -> Color:
    if spec is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(spec)


def _col(ref, name) -> np.ndarray:
    return np.asarray(ref.series(name), dtype="float64")


def _xy_log(ctx) -> tuple[bool, bool]:
    """Whether this surface's axes are log — pyqtgraph pre-transforms the data
    (Approach A), so the x/y renderers `logify` what they plot ([D59] increment 2)."""
    return ctx.x_scale == "log", ctx.y_scale == "log"


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
    kwargs = {"pen": None, "useCache": True, "hoverable": True,
              "symbol": _MARKER[element.marker]}
    kwargs["size"] = (
        _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6)
    )
    legend = None
    alpha = element.alpha
    if element.color_by is not None:
        rgba, legend = _color_mapping(element, d, ctx.theme)
        kwargs["brush"] = [
            pg.mkBrush(r, g, b, int(round(a * alpha))) for r, g, b, a in (_u8(c) for c in rgba)
        ]
    else:
        color = _color(element.color, ctx.theme).qt()
        color.setAlphaF(alpha)
        kwargs["brush"] = pg.mkBrush(color)
    x_log, y_log = _xy_log(ctx)
    item = pg.ScatterPlotItem(x=logify(_col(d, "x"), x_log), y=logify(_col(d, "y"), y_log),
                              **kwargs)
    ctx.parent_axes.addItem(item)
    if legend is not None and ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    return item


def render_curve(element: Curve, ctx):
    d = element.data
    color = _color(element.color, ctx.theme).qt()
    color.setAlphaF(element.alpha)
    pen = pg.mkPen(color, width=element.line_width, style=_PEN_STYLE[element.line_style])
    x_log, y_log = _xy_log(ctx)
    # connect="finite" breaks the line at NaN — the mask logify leaves for
    # non-positive values under log (and any NaN already in the data).
    item = pg.PlotCurveItem(x=logify(_col(d, "x"), x_log), y=logify(_col(d, "y"), y_log),
                            pen=pen, connect="finite")
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
    x_log, y_log = _xy_log(ctx)
    # under log-y bar *heights* are log10'd (baseline sits at data 1); a proper
    # clipped-baseline treatment is deferred with the rest of the bar vocabulary.
    item = pg.BarGraphItem(x=logify(x, x_log), height=logify(height, y_log),
                           width=0.6, brush=brush)
    ctx.parent_axes.addItem(item)
    return item


def render_histogram(element: Histogram, ctx):
    vals = _col(element.data, "column")
    bins = element.bins if isinstance(element.bins, int) else "auto"
    counts, edges = np.histogram(vals, bins=bins, density=element.density)
    centers = (edges[:-1] + edges[1:]) / 2.0
    width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0
    x_log, y_log = _xy_log(ctx)
    item = pg.BarGraphItem(x=logify(centers, x_log), height=logify(counts, y_log),
                           width=width * 0.95,
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
    if result is not None and result.legend is not None and ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        # category key / colorbar (C3)
        add_legend(ctx.parent_axes, result.legend, ctx.theme, ctx.legend_position)
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
    position = ctx.legend_position
    holder = SimpleNamespace(aggregate=getattr(element, "_raster_aggregate", None))
    target = PgRasterTarget(item, vb)
    refresh_legend = (  # refresh on re-aggregation (C3); a suppressed legend stays off
        (lambda lg: add_legend(plot, lg, theme, position)) if ctx.show_legend
        else (lambda lg: None)
    )
    controller = RasterController(
        source=source, target=target,
        rasterize=themed_rasterize(theme.palette, palettes.get("viridis"), _raster_title(element)),
        parent=vb, on_aggregate=lambda agg: setattr(holder, "aggregate", agg),
        on_legend=refresh_legend,
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
    x_log, y_log = _xy_log(ctx)
    y, hi, lo = _col(d, "y"), _col(d, "err_hi"), _col(d, "err_lo")
    ly = logify(y, y_log)
    if y_log:
        # error extents are deltas — recompute them in exponent space so the
        # whiskers land at log10(y ± err), not log10(y) ± err.
        top, bottom = logify(y + hi, True) - ly, ly - logify(y - lo, True)
    else:
        top, bottom = hi, lo
    item = pg.ErrorBarItem(
        x=logify(_col(d, "x"), x_log), y=ly, top=top, bottom=bottom, beam=0.0,
    )
    ctx.parent_axes.addItem(item)
    return item


def render_spread(element: Spread, ctx):
    d = element.data
    x_log, y_log = _xy_log(ctx)
    x = logify(_col(d, "x"), x_log)
    lo = pg.PlotDataItem(x, logify(_col(d, "y_lo"), y_log))
    hi = pg.PlotDataItem(x, logify(_col(d, "y_hi"), y_log))
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

# Recommended options each renderer above actually consumes (spec §3.4 / [D51]).
# Anything in an element's RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
# Keep in sync with the renderers — the conformance test guards this.
HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker", "label"}),
    Curve: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Bars: frozenset({"color", "label"}),                           # not group/orient
    Histogram: frozenset({"bins", "density", "color", "label"}),
    Image: frozenset(),                                            # colormap/interpolation unwired
    Heatmap: frozenset(),                                          # colormap/aggregator unwired
    ErrorBars: frozenset({"label"}),                               # color/direction unwired
    Spread: frozenset({"color", "alpha", "label"}),
}
