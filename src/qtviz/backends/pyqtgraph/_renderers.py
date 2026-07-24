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
    BoxPlot,
    Curve,
    ErrorBars,
    Heatmap,
    Histogram,
    HLine,
    Image,
    Scatter,
    Span,
    Spread,
    Text,
    Violin,
    VLine,
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
        color = _color(element.color, ctx.theme, ctx.series_index).qt()
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
    color = _color(element.color, ctx.theme, ctx.series_index).qt()
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
    if element.group is not None:
        return _render_group_bars(element, ctx)
    d = element.data
    height = _col(d, "y")
    try:
        x = _col(d, "x")
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")  # categorical → indices
    brush = _color(element.color, ctx.theme, ctx.series_index).qt()
    x_log, y_log = _xy_log(ctx)
    # under log-y bar *heights* are log10'd (baseline sits at data 1); a proper
    # clipped-baseline treatment is deferred with the rest of the bar vocabulary.
    item = pg.BarGraphItem(x=logify(x, x_log), height=logify(height, y_log),
                           width=0.6, brush=brush)
    ctx.parent_axes.addItem(item)
    return item


def _bar_positions(xs) -> tuple[np.ndarray, bool]:
    """Category base positions: numeric x uses the values; strings use 0..n-1
    (the caller sets tick labels)."""
    numeric = np.issubdtype(xs.dtype, np.number)
    return (xs.astype("float64") if numeric else np.arange(len(xs), dtype="float64")), numeric


def _log_base_top(bases, tops, y_log: bool):
    """Stacked-bar segment bounds under log-y: computed in *data* space, then to
    exponent space. A zero base keeps the (data 1) baseline convention without a
    spurious non-positive warning."""
    if not y_log:
        return bases, tops
    lb = np.zeros_like(bases)
    positive = bases > 0
    lb[positive] = np.log10(bases[positive])
    return lb, logify(tops, True)


def _render_group_bars(element: Bars, ctx):
    """One BarGraphItem per group ([D68]): side-by-side offsets (grouped) or
    cumulative data-space bases (stacked); palette per group in category order
    (`category_swatches` — same rule as color_by) + a categorical group legend."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    xs, gs, mat = group_bars(np.asarray(d.series("x")), _col(d, "y"),
                             np.asarray(d.series("group")))
    pos, numeric = _bar_positions(xs)
    if not numeric:
        ctx.parent_axes.getAxis("bottom").setTicks(
            [[(float(i), str(c)) for i, c in enumerate(xs)]]
        )
    swatches = category_swatches(gs, ctx.theme.palette)
    _x_log, y_log = _xy_log(ctx)
    items = []
    if element.mode == "grouped":
        total_w = 0.8
        w = total_w / len(gs)
        for gi in range(len(gs)):
            offs = pos - total_w / 2 + w / 2 + gi * w
            items.append(pg.BarGraphItem(x=offs, height=logify(mat[gi], y_log),
                                         width=w * 0.95, brush=swatches[gi].qt()))
    else:  # stacked
        bases = np.zeros(len(xs))
        for gi in range(len(gs)):
            tops = bases + mat[gi]
            y0, y1 = _log_base_top(bases, tops, y_log)
            items.append(pg.BarGraphItem(x=pos, y0=y0, y1=y1, width=0.6,
                                         brush=swatches[gi].qt()))
            bases = tops
    for item in items:
        ctx.parent_axes.addItem(item)
    if ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        legend = Legend(kind="categorical", title=element.group,
                        entries=tuple((str(g), swatches[i]) for i, g in enumerate(gs)))
        add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    return items


def render_histogram(element: Histogram, ctx):
    vals = _col(element.data, "column")
    bins = element.bins if isinstance(element.bins, int) else "auto"
    counts, edges = np.histogram(vals, bins=bins, density=element.density)
    centers = (edges[:-1] + edges[1:]) / 2.0
    width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0
    x_log, y_log = _xy_log(ctx)
    item = pg.BarGraphItem(x=logify(centers, x_log), height=logify(counts, y_log),
                           width=width * 0.95,
                           brush=_color(element.color, ctx.theme, ctx.series_index).qt())
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
    from ...core._stats import grid_reduce  # noqa: PLC0415

    d = element.data
    _xs, _ys, grid = grid_reduce(d.series("x"), d.series("y"), _col(d, "z"),
                                 element.aggregator)  # real reduction ([D69])
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
    brush = _color(element.color, ctx.theme, ctx.series_index).qt()
    brush.setAlphaF(element.alpha)
    fill = pg.FillBetweenItem(lo, hi, brush=brush)
    for it in (lo, hi, fill):
        ctx.parent_axes.addItem(it)
    return fill


def _ref_color(spec, theme) -> Color:
    """Annotation default: the theme foreground — a reference is chrome, not a
    series, so it must not look like palette data ([D70])."""
    return Color(spec) if spec is not None else theme.foreground


def _ref_scalar(value: float, is_log: bool) -> float | None:
    """A single annotation coordinate through the axis scale (R1): logified under
    log; `None` (drop, already warned) when non-positive makes it non-finite."""
    v = logify(np.array([value], dtype="float64"), is_log)[0]
    return float(v) if np.isfinite(v) else None


def render_hline(element: HLine, ctx):
    _x_log, y_log = _xy_log(ctx)
    pos = _ref_scalar(element.y, y_log)
    if pos is None:
        return None
    color = _ref_color(element.color, ctx.theme).qt()
    color.setAlphaF(element.alpha)
    pen = pg.mkPen(color, width=element.line_width, style=_PEN_STYLE[element.line_style])
    item = pg.InfiniteLine(pos=pos, angle=0, pen=pen, movable=False)
    ctx.parent_axes.addItem(item)
    return item


def render_vline(element: VLine, ctx):
    x_log, _y_log = _xy_log(ctx)
    pos = _ref_scalar(element.x, x_log)
    if pos is None:
        return None
    color = _ref_color(element.color, ctx.theme).qt()
    color.setAlphaF(element.alpha)
    pen = pg.mkPen(color, width=element.line_width, style=_PEN_STYLE[element.line_style])
    item = pg.InfiniteLine(pos=pos, angle=90, pen=pen, movable=False)
    ctx.parent_axes.addItem(item)
    return item


def render_span(element: Span, ctx):
    x_log, y_log = _xy_log(ctx)
    is_h = element.orient == "h"          # a y-range band across the full width
    lo = _ref_scalar(element.lo, y_log if is_h else x_log)
    hi = _ref_scalar(element.hi, y_log if is_h else x_log)
    if lo is None or hi is None:
        return None
    color = _ref_color(element.color, ctx.theme).qt()
    color.setAlphaF(element.alpha)
    item = pg.LinearRegionItem(
        values=(lo, hi), orientation="horizontal" if is_h else "vertical",
        movable=False, brush=pg.mkBrush(color), pen=pg.mkPen(None),
    )
    ctx.parent_axes.addItem(item)
    return item


_TEXT_ANCHOR = {"center": (0.5, 0.5), "left": (0.0, 0.5), "right": (1.0, 0.5)}


def render_text(element: Text, ctx):
    x_log, y_log = _xy_log(ctx)
    px, py = _ref_scalar(element.x, x_log), _ref_scalar(element.y, y_log)
    if px is None or py is None:
        return None
    item = pg.TextItem(element.text, color=_ref_color(element.color, ctx.theme).qt(),
                       anchor=_TEXT_ANCHOR[element.anchor])
    if element.size is not None:
        font = item.textItem.font()
        font.setPointSizeF(float(element.size))
        item.setFont(font)
    ctx.parent_axes.addItem(item)
    item.setPos(px, py)
    return item



def _dist_prep(element, ctx):
    """Shared BoxPlot/Violin prep ([D67]): per-category value groups, base
    positions, palette swatches (category order = color_by rule), tick labels,
    and the categorical legend when `by` is set."""
    from ...core._stats import split_by  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    cats, groups = split_by(d.series("column"),
                            d.series("by") if element.by is not None else None)
    pos = np.arange(len(groups), dtype="float64")
    if cats is not None:
        swatches = category_swatches(cats, ctx.theme.palette)
        ctx.parent_axes.getAxis("bottom").setTicks(
            [[(float(i), str(c)) for i, c in enumerate(cats)]]
        )
        if ctx.show_legend:
            from ._legend import add_legend  # noqa: PLC0415

            legend = Legend(kind="categorical", title=element.by,
                            entries=tuple((str(c), swatches[i]) for i, c in enumerate(cats)))
            add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    else:
        swatches = [_color(element.color, ctx.theme, ctx.series_index)] * len(groups)
    return groups, pos, swatches


def render_boxplot(element: BoxPlot, ctx):
    """Boxes from the shared `box_stats` ([D67]) — body (BarGraphItem), whiskers/
    caps/medians (one NaN-separated PlotCurveItem), outlier points."""
    from ...core._stats import box_stats  # noqa: PLC0415

    groups, pos, swatches = _dist_prep(element, ctx)
    stats = [box_stats(g) for g in groups]
    _x_log, y_log = _xy_log(ctx)

    def ly(vals):
        return logify(np.asarray(vals, dtype="float64"), y_log)

    q1s, q3s = ly([s.q1 for s in stats]), ly([s.q3 for s in stats])
    lows, highs = ly([s.lo_whisker for s in stats]), ly([s.hi_whisker for s in stats])
    meds = ly([s.median for s in stats])
    brushes = []
    for sw in swatches:
        c = sw.qt()
        c.setAlphaF(element.alpha)
        brushes.append(pg.mkBrush(c))
    fg = ctx.theme.foreground.qt()
    boxes = pg.BarGraphItem(x=pos, y0=q1s, y1=q3s, width=0.5,
                            brushes=brushes, pen=pg.mkPen(fg))
    seg_x: list[float] = []
    seg_y: list[float] = []

    def seg(x0, y0, x1, y1):
        seg_x.extend([x0, x1, np.nan])
        seg_y.extend([y0, y1, np.nan])

    for i in range(len(stats)):
        seg(pos[i], q3s[i], pos[i], highs[i])                  # upper whisker
        seg(pos[i], q1s[i], pos[i], lows[i])                   # lower whisker
        seg(pos[i] - 0.15, highs[i], pos[i] + 0.15, highs[i])  # caps
        seg(pos[i] - 0.15, lows[i], pos[i] + 0.15, lows[i])
        seg(pos[i] - 0.25, meds[i], pos[i] + 0.25, meds[i])    # median
    lines = pg.PlotCurveItem(np.asarray(seg_x), np.asarray(seg_y),
                             pen=pg.mkPen(fg, width=1.5), connect="finite")
    out_x = [np.full(len(s.outliers), pos[i]) for i, s in enumerate(stats) if len(s.outliers)]
    out_y = [s.outliers for s in stats if len(s.outliers)]
    fliers = pg.ScatterPlotItem(
        x=np.concatenate(out_x) if out_x else np.array([]),
        y=ly(np.concatenate(out_y)) if out_y else np.array([]),
        size=5, brush=pg.mkBrush(fg), pen=None,
    )
    for item in (boxes, lines, fliers):
        ctx.parent_axes.addItem(item)
    return [boxes, lines, fliers]


def render_violin(element: Violin, ctx):
    """Silhouettes from the shared `kde` ([D67]) — one filled polygon per group
    (QGraphicsPathItem; pyqtgraph has no native polygon-fill plot item)."""
    from PySide6.QtWidgets import QGraphicsPathItem  # noqa: PLC0415

    from ...core._stats import kde  # noqa: PLC0415

    groups, pos, swatches = _dist_prep(element, ctx)
    _x_log, y_log = _xy_log(ctx)
    items = []
    for i, g in enumerate(groups):
        grid, dens = kde(g)
        half = dens / (dens.max() or 1.0) * 0.4
        xs_p = np.concatenate([pos[i] + half, (pos[i] - half)[::-1]])
        ys_p = logify(np.concatenate([grid, grid[::-1]]), y_log)
        item = QGraphicsPathItem(pg.arrayToQPath(xs_p, ys_p))
        c = swatches[i].qt()
        c.setAlphaF(element.alpha)
        item.setBrush(pg.mkBrush(c))
        item.setPen(pg.mkPen(swatches[i].qt()))
        ctx.parent_axes.addItem(item)
        items.append(item)
    return items


RENDERERS = {
    Scatter: render_scatter,
    Curve: render_curve,
    Bars: render_bars,
    Histogram: render_histogram,
    Image: render_image,
    Heatmap: render_heatmap,
    ErrorBars: render_errorbars,
    Spread: render_spread,
    HLine: render_hline,
    VLine: render_vline,
    Span: render_span,
    Text: render_text,
    BoxPlot: render_boxplot,
    Violin: render_violin,
}

# Recommended options each renderer above actually consumes (spec §3.4 / [D51]).
# Anything in an element's RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
# Keep in sync with the renderers — the conformance test guards this.
HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker", "label"}),
    Curve: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Bars: frozenset({"color", "group", "label"}),                  # not orient
    Histogram: frozenset({"bins", "density", "color", "label"}),
    Image: frozenset(),                                            # colormap/interpolation unwired
    Heatmap: frozenset({"aggregator"}),                            # colormap unwired
    ErrorBars: frozenset({"label"}),                               # color/direction unwired
    Spread: frozenset({"color", "alpha", "label"}),
    HLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    VLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Span: frozenset({"color", "alpha", "label"}),
    Text: frozenset({"color", "size", "anchor"}),
    BoxPlot: frozenset({"by", "color", "alpha", "label"}),
    Violin: frozenset({"by", "color", "alpha", "label"}),
}
