"""pyqtgraph element renderers (spec §4.1).

One function per Element type. By the time a renderer runs, the resolve pipeline
(D14) has replaced the Element's data with a role-keyed eager ref, so renderers
read channels by their fixed **role** name (`"x"`, `"y"`, …) — never the user's
accessor, which may be a string, Expression, callable, or array.
"""
# mypy: disable-error-code="attr-defined, assignment"
# (renderers run post-resolve: a tabular element holds a TabularRef, a
#  gridded one a GriddedRef — a shape invariant the static types cannot see)

from __future__ import annotations

from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt

from ...core._scales import logify
from ...core.color import Color
from ...core.encoding import channel_title
from ...elements import (
    Area,
    Bars,
    BoxPlot,
    Contour,
    Curve,
    Ecdf,
    ErrorBars,
    Heatmap,
    Histogram,
    Image,
    Mesh,
    Scatter,
    Spread,
    Violin,
)

# qtviz marker vocabulary → pyqtgraph symbol codes / Qt pen styles ([D51]/[D99]).
# NOTE: pg "t" points DOWN — "triangle" is "t1" (up) to match mpl "^"/Plotly
# "triangle-up" (a pre-existing cross-backend mismatch fixed in [D99]).
_MARKER = {"circle": "o", "square": "s", "triangle": "t1", "triangle_down": "t",
           "diamond": "d", "cross": "x", "plus": "+", "star": "star",
           "pentagon": "p", "hexagon": "h"}
_PEN_STYLE = {
    "solid": Qt.SolidLine, "dashed": Qt.DashLine,
    "dotted": Qt.DotLine, "dashdot": Qt.DashDotLine,
}


def _mk_pen(color, width: float, style):
    """A pen from the [D99] line-style vocabulary: named Qt style, or a dash
    tuple in points (Qt dash patterns are in units of the pen width)."""
    if isinstance(style, str):
        return pg.mkPen(color, width=width, style=_PEN_STYLE[style])
    pen = pg.mkPen(color, width=width)
    pen.setDashPattern([v / max(width, 0.5) for v in style])
    return pen


def _color(spec, theme, idx: int = 0) -> Color:
    if spec is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(spec)


def _col(ref, name) -> np.ndarray:
    from ...core._time import as_float_seconds  # noqa: PLC0415

    return as_float_seconds(ref.series(name))  # datetime64 → epoch s ([D94])


def _xy_log(ctx) -> tuple[bool, bool]:
    """Whether this surface's axes are log — pyqtgraph pre-transforms the data
    (Approach A), so the x/y renderers `logify` what they plot ([D59] increment 2)."""
    return ctx.x_scale == "log", ctx.y_scale == "log"


def _u8(rgba_row) -> tuple[int, int, int, int]:
    r, g, b, a = (int(round(v * 255)) for v in rgba_row)
    return (r, g, b, a)


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
        continuous_palette=palettes.get("viridis"), title=channel_title(element.color_by),
        norm=getattr(element, "color_norm", "linear"),
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


# qtviz step vocabulary → pg stepMode ([D84]): pg assigns y[i] to the named
# edge of the [x[i], x[i+1]) interval, so data "post" is pg "left".
_STEP_PG = {"pre": "right", "mid": "center", "post": "left"}


def _mid_edges(x: np.ndarray) -> np.ndarray:
    """Bin edges for a mid-step curve (pg stepMode="center" wants n+1 edges):
    midpoints between samples, end bins extended symmetrically."""
    if len(x) < 2:
        return np.array([x[0] - 0.5, x[0] + 0.5]) if len(x) else np.array([0.0, 1.0])
    mid = (x[:-1] + x[1:]) / 2.0
    return np.concatenate(([2 * x[0] - mid[0]], mid, [2 * x[-1] - mid[-1]]))


def _warn_continuous_curve(backend: str) -> None:
    import warnings  # noqa: PLC0415

    from ...errors import QtvizWarning  # noqa: PLC0415

    warnings.warn(f"{backend}: continuous Curve color_by (a per-segment gradient "
                  "line) is matplotlib-only; drawing a single-color line.",
                  QtvizWarning, stacklevel=2)


def _curve_color_by(element: Curve, ctx):
    """Categorical per-segment coloring via the shared core split ([D100]);
    a continuous column warns (no pg gradient-polyline primitive) and draws
    the palette color."""
    from ...core._stats import categorical_line_split  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches, is_categorical  # noqa: PLC0415

    d = element.data
    values = np.asarray(d.series("color"))
    if not is_categorical(values):
        _warn_continuous_curve("pyqtgraph")
        return None  # fall through to the plain-line path
    x_log, y_log = _xy_log(ctx)
    x, y = _col(d, "x"), _col(d, "y")
    cats, parts = categorical_line_split(x, y, values)
    swatches = category_swatches(cats, ctx.theme.palette)
    items = []
    for (xs, ys), sw in zip(parts, swatches, strict=True):
        c = sw.qt()
        c.setAlphaF(element.alpha)
        item = pg.PlotCurveItem(x=logify(xs, x_log), y=logify(ys, y_log),
                                pen=_mk_pen(c, element.line_width, element.line_style),
                                connect="finite")
        ctx.parent_axes.addItem(item)
        items.append(item)
    if ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        legend = Legend(kind="categorical", title=channel_title(element.color_by),
                        entries=tuple((str(c), sw)
                                      for c, sw in zip(cats, swatches, strict=True)))
        add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    return items


def render_curve(element: Curve, ctx):
    if element.color_by is not None:
        items = _curve_color_by(element, ctx)
        if items is not None:
            return items
    d = element.data
    color = _color(element.color, ctx.theme, ctx.series_index).qt()
    color.setAlphaF(element.alpha)
    pen = _mk_pen(color, element.line_width, element.line_style)
    x_log, y_log = _xy_log(ctx)
    x, y = _col(d, "x"), _col(d, "y")
    # connect="finite" breaks the line at NaN — the mask logify leaves for
    # non-positive values under log (and any NaN already in the data).
    kwargs: dict = {"pen": pen, "connect": "finite"}
    if element.step is not None:
        kwargs["stepMode"] = _STEP_PG[element.step]
        if element.step == "mid":
            x = _mid_edges(x)  # edges in data space, then logified below
    lx, ly = logify(x, x_log), logify(y, y_log)
    every = element.marker_every
    if element.marker is not None and element.step != "mid" and every == 1:
        item = pg.PlotDataItem(x=lx, y=ly, symbol=_MARKER[element.marker],
                               symbolBrush=color, symbolPen=None, symbolSize=7, **kwargs)
    else:
        item = pg.PlotCurveItem(x=lx, y=ly, **kwargs)
        if element.marker is not None:
            # mid-step symbols sit at data points (not edges); marker_every>1
            # thins them ([D99]) — either way a separate points item
            dots = pg.ScatterPlotItem(
                x=logify(_col(d, "x"), x_log)[::every], y=ly[::every],
                symbol=_MARKER[element.marker], brush=color, pen=None, size=7)
            ctx.parent_axes.addItem(dots)
    ctx.parent_axes.addItem(item)
    return item


def _bar_label_items(ctx, positions, values, tops, element, *, inside=False) -> None:
    """Value labels beside/inside bars ([D98]) — formatted via [D86]."""
    if element.annotate is None:
        return
    from ...core._ticks import format_tick  # noqa: PLC0415

    spec = element.annotate if element.annotate != "auto" else "g"
    horizontal = element.orient == "h"
    fg = ctx.theme.foreground.qt()
    for pos, val, top in zip(positions, values, tops, strict=True):
        item = pg.TextItem(format_tick(float(val), spec), color=fg,
                           anchor=((0.5, 0.5) if inside
                                   else (0.0, 0.5) if horizontal
                                   else (0.5, 1.0)))
        font = item.textItem.font()
        font.setPointSizeF(8.0)
        item.setFont(font)
        ctx.parent_axes.addItem(item)
        item.setPos(*((float(top), float(pos)) if horizontal
                      else (float(pos), float(top))))


def render_bars(element: Bars, ctx):
    if element.by is not None:
        return _render_group_bars(element, ctx)
    d = element.data
    height = _col(d, "y")
    try:
        x = _col(d, "x")
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")  # categorical → indices
    brush = _color(element.color, ctx.theme, ctx.series_index).qt()
    x_log, y_log = _xy_log(ctx)
    # under log the bar *lengths* are log10'd (baseline sits at data 1); a proper
    # clipped-baseline treatment is deferred with the rest of the bar vocabulary.
    brushes = None
    if element.color_by is not None:  # per-bar colors ([D100])
        rgba, legend = _color_mapping(element, d, ctx.theme)
        brushes = [pg.mkBrush(*_u8(c)) for c in rgba]
        if ctx.show_legend:
            from ._legend import add_legend  # noqa: PLC0415

            add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    geo = ({"y": logify(x, y_log), "x0": 0.0, "x1": logify(height, x_log),
            "height": 0.6} if element.orient == "h"
           else {"x": logify(x, x_log), "height": logify(height, y_log),
                 "width": 0.6})
    item = pg.BarGraphItem(**geo, **({"brushes": brushes} if brushes is not None
                                     else {"brush": brush}))
    if element.orient == "h":
        _bar_label_items(ctx, logify(x, y_log), height, logify(height, x_log), element)
    else:
        _bar_label_items(ctx, logify(x, x_log), height, logify(height, y_log), element)
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
                             np.asarray(d.series("by")))
    pos, numeric = _bar_positions(xs)
    horizontal = element.orient == "h"  # positions on y, lengths on x ([D85])
    if not numeric:
        ctx.parent_axes.getAxis("left" if horizontal else "bottom").setTicks(
            [[(float(i), str(c)) for i, c in enumerate(xs)]]
        )
    swatches = category_swatches(gs, ctx.theme.palette)
    x_log, y_log = _xy_log(ctx)
    val_log = x_log if horizontal else y_log
    items = []
    if element.mode == "grouped":
        total_w = 0.8
        w = total_w / len(gs)
        for gi in range(len(gs)):
            offs = pos - total_w / 2 + w / 2 + gi * w
            vals = logify(mat[gi], val_log)
            geo = ({"y": offs, "x0": 0.0, "x1": vals, "height": w * 0.95} if horizontal
                   else {"x": offs, "height": vals, "width": w * 0.95})
            items.append(pg.BarGraphItem(brush=swatches[gi].qt(), **geo))
    else:  # stacked
        bases = np.zeros(len(xs))
        for gi in range(len(gs)):
            tops = bases + mat[gi]
            v0, v1 = _log_base_top(bases, tops, val_log)
            geo = ({"y": pos, "x0": v0, "x1": v1, "height": 0.6} if horizontal
                   else {"x": pos, "y0": v0, "y1": v1, "width": 0.6})
            items.append(pg.BarGraphItem(brush=swatches[gi].qt(), **geo))
            bases = tops
    for item in items:
        ctx.parent_axes.addItem(item)
    if ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        legend = Legend(kind="categorical", title=channel_title(element.by),
                        entries=tuple((str(g), swatches[i]) for i, g in enumerate(gs)))
        add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    return items


def render_histogram(element: Histogram, ctx):
    from ...core._stats import histogram  # noqa: PLC0415

    counts, edges = histogram(_col(element.data, "value"), element.bins,
                              density=element.density)  # shared binning ([D93])
    hist_color = _color(element.color, ctx.theme, ctx.series_index).qt()
    hist_color.setAlphaF(element.alpha)
    centers = (edges[:-1] + edges[1:]) / 2.0
    width = float(edges[1] - edges[0]) if len(edges) > 1 else 1.0
    x_log, y_log = _xy_log(ctx)
    item = pg.BarGraphItem(x=logify(centers, x_log), height=logify(counts, y_log),
                           width=width * 0.95, brush=pg.mkBrush(hist_color))
    ctx.parent_axes.addItem(item)
    return item


def render_image(element: Image, ctx):
    from PySide6.QtCore import QRectF  # noqa: PLC0415

    agg = getattr(element, "_raster_agg", None)
    legend = None
    if agg is not None:  # datashaded raster: shade + legend with the View's Theme (C2/C3)
        result = _shade_raster(element, agg, ctx.theme)
        item = pg.ImageItem(result.rgba, axisOrder="row-major")
        legend = result.legend
    elif getattr(element, "_grid_source", None) is not None:
        # decimated lazy grid ([D74]): shade with the same ramp the regrid loop
        # uses, so the first frame matches every re-grid after it ([D75])
        from ...core.palette import palettes  # noqa: PLC0415
        from ...data.regrid import shade_values  # noqa: PLC0415

        rgba, legend = shade_values(element.data.grid().values, palettes.get("viridis"))
        item = pg.ImageItem(rgba, axisOrder="row-major")
    else:
        values = np.asarray(element.data.grid().values)
        if values.ndim == 3:  # RGBA raster (e.g. a user-built image): row 0 = ymin
            item = pg.ImageItem(values, axisOrder="row-major")
        else:
            display, levels, norm_legend = _norm_display(  # ([D105])
                element, np.asarray(values, dtype="float64"), ctx)
            item = pg.ImageItem(display, axisOrder="row-major")
            item.setLookupTable(_pg_lut(element.colormap))  # ([D92])
            if levels is not None:
                item.setLevels(levels)
            if norm_legend is not None and ctx.show_legend:
                from ._legend import add_legend  # noqa: PLC0415

                add_legend(ctx.parent_axes, norm_legend, ctx.theme,
                           ctx.legend_position)
    x0, y0, x1, y1 = element.extent
    item.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    ctx.parent_axes.addItem(item)
    if legend is not None and ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        # category key / colorbar (C3)
        add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    _wire_dynamic_raster(element, item, ctx)
    _wire_dynamic_regrid(element, item, ctx)
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
    controller.element_id = element.id  # streaming refresh routes by id ([D77])
    if not hasattr(vb, "_qtviz_rasters"):
        vb._qtviz_rasters = []
    vb._qtviz_rasters.append(controller)
    vb._qtviz_rasters.append(wire_raster_hover(vb, element.id, ctx.event_bus, holder))



def _wire_dynamic_regrid(element, item, ctx) -> None:
    """Viewport-regrid loop for a decimated lazy grid ([D75]) — the same
    RasterController/target/debounce/stale-drop the datashader loop uses, with
    `regrid` (window → decimate → shade) as the rasterize. Mutually exclusive
    with `_wire_dynamic_raster` by construction (`_raster_source` vs
    `_grid_source` never co-exist)."""
    source = getattr(element, "_grid_source", None)
    if source is None:
        return
    from ...core.palette import palettes  # noqa: PLC0415
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...data.regrid import make_regrid  # noqa: PLC0415
    from ._legend import add_legend  # noqa: PLC0415
    from ._raster import PgRasterTarget  # noqa: PLC0415

    vb = ctx.parent_axes.getViewBox()
    plot = ctx.parent_axes
    theme = ctx.theme
    position = ctx.legend_position
    refresh_legend = (  # vmin/vmax track the visible window (C3)
        (lambda lg: add_legend(plot, lg, theme, position)) if ctx.show_legend
        else (lambda lg: None)
    )
    controller = RasterController(
        source=source, target=PgRasterTarget(item, vb),
        rasterize=make_regrid(element.extent, palettes.get("viridis")),
        parent=vb, on_legend=refresh_legend,
    )
    if not hasattr(vb, "_qtviz_rasters"):
        vb._qtviz_rasters = []
    vb._qtviz_rasters.append(controller)


def _pg_lut(name: str):
    """256-entry LUT for a named colormap ([D92]): pg's own maps first, then
    matplotlib's registry when importable, else warn → viridis."""
    for source in (None, "matplotlib"):
        try:
            return pg.colormap.get(name, source=source).getLookupTable(nPts=256)
        except Exception:  # noqa: BLE001 — unknown name / mpl not installed
            continue
    import warnings  # noqa: PLC0415

    from ...errors import QtvizWarning  # noqa: PLC0415

    warnings.warn(f"pyqtgraph: no colormap named {name!r}; using 'viridis'",
                  QtvizWarning, stacklevel=2)
    return pg.colormap.get("viridis").getLookupTable(nPts=256)


def _norm_display(element, values, ctx):
    """[D105] for pg: normalized values with (0, 1) levels + the [D48]-honest
    legend (gradient colorbar for a linear norm, endpoints-only key for
    log/power — pg's gradient ticks interpolate linearly, which would lie)."""
    from ...core.encoding import Legend, norm_engaged, normalize_values  # noqa: PLC0415

    if not norm_engaged(element):
        return values, None, None
    normed, lo, hi = normalize_values(
        values, norm=element.norm, vmin=element.vmin, vmax=element.vmax,
        gamma=element.gamma, linthresh=getattr(element, "linthresh", 1.0),
        levels=getattr(element, "levels", None))
    lut = _pg_lut(element.colormap)
    step = max(len(lut) // 8, 1)
    ramp = tuple(Color(f"#{r:02x}{g:02x}{b:02x}") for r, g, b in
                 (row[:3] for row in lut[::step]))
    legend = Legend(kind="continuous", vmin=lo, vmax=hi, ramp=ramp,
                    linear=element.norm == "linear")
    return normed, (0.0, 1.0), legend


def _heat_extent(plot, centers, axis: str) -> tuple[float, float]:
    """Data-space extent for one heatmap axis ([D92]) — the pg sibling of the
    matplotlib helper: numeric centers place cells at their values; categorical
    centers use index positions + tick labels."""
    from ...core._stats import cell_extent  # noqa: PLC0415

    arr = np.asarray(centers)
    if np.issubdtype(arr.dtype, np.number):
        return cell_extent(arr)
    plot.getAxis("bottom" if axis == "x" else "left").setTicks(
        [[(float(i), str(c)) for i, c in enumerate(arr)]])
    return (-0.5, len(arr) - 0.5)


def render_heatmap(element: Heatmap, ctx):
    from PySide6.QtCore import QRectF  # noqa: PLC0415

    from ...core._stats import grid_reduce  # noqa: PLC0415

    d = element.data
    xs, ys, grid = grid_reduce(d.series("x"), d.series("y"), _col(d, "z"),
                               element.aggregator)  # real reduction ([D69])
    raw_grid = grid  # labels state raw values, not normalized ones ([D113])
    grid, levels, norm_legend = _norm_display(element, grid, ctx)  # ([D105])
    # row-major: grid[j, i] is (ys[j], xs[i]) — the pg default (col-major) drew
    # every heatmap transposed relative to matplotlib/webengine ([D92]).
    item = pg.ImageItem(grid, axisOrder="row-major")
    item.setLookupTable(_pg_lut(element.colormap))
    if levels is not None:
        item.setLevels(levels)
    if norm_legend is not None and ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        add_legend(ctx.parent_axes, norm_legend, ctx.theme, ctx.legend_position)
    x0, x1 = _heat_extent(ctx.parent_axes, xs, "x")
    y0, y1 = _heat_extent(ctx.parent_axes, ys, "y")
    item.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))
    ctx.parent_axes.addItem(item)
    labels = element.resolved_cell_labels(xs, ys, raw_grid, ctx.theme)  # ([D113])
    for lb in labels:
        text = pg.TextItem(lb.text, color=lb.color.qt(), anchor=(0.5, 0.5))
        text.setPos(lb.x, lb.y)
        ctx.parent_axes.addItem(text)
    return item


def _log_deltas(center, lo, hi, is_log: bool, lc):
    """Whisker extents around `center` for one axis: error extents are deltas —
    under log they're recomputed in exponent space so the whiskers land at
    log10(v ± err), not log10(v) ± err."""
    if not is_log:
        return lo, hi
    return lc - logify(center - lo, True), logify(center + hi, True) - lc


def _pg_colormap(name: str):
    """The pg ColorMap for a name — same resolution/fallback contract as
    `_pg_lut` (pg's maps, then matplotlib's registry, warn → viridis)."""
    for source in (None, "matplotlib"):
        try:
            return pg.colormap.get(name, source=source)
        except Exception:  # noqa: BLE001
            continue
    import warnings  # noqa: PLC0415

    from ...errors import QtvizWarning  # noqa: PLC0415

    warnings.warn(f"pyqtgraph: no colormap named {name!r}; using 'viridis'",
                  QtvizWarning, stacklevel=2)
    return pg.colormap.get("viridis")





def render_mesh(element: Mesh, ctx):
    """Non-uniform rectilinear grid ([D106]) via `PColorMeshItem` (spiked:
    edge-corner meshgrids, explicit levels). Shares the [D105] norm path."""
    values = element.check_shape(element.data.grid().values)
    display, levels, norm_legend = _norm_display(element, values, ctx)
    xg, yg = np.meshgrid(np.asarray(element.x), np.asarray(element.y))
    kwargs: dict = {"colorMap": _pg_colormap(element.colormap)}
    if levels is not None:
        kwargs.update(levels=levels, enableAutoLevels=False)
    item = pg.PColorMeshItem(xg, yg, display, **kwargs)
    ctx.parent_axes.addItem(item)
    if norm_legend is not None and ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        add_legend(ctx.parent_axes, norm_legend, ctx.theme, ctx.legend_position)
    return item


def render_contour(element: Contour, ctx):
    """Iso-lines over a grid ([D89]) via `IsocurveItem` — one item per shared
    core level, colormap-colored, index coords mapped onto `bounds` the way
    matplotlib's `extent` maps them (first/last sample on the edges). `filled`
    is not honored here (no pg primitive) and warns."""
    from PySide6.QtGui import QColor, QTransform  # noqa: PLC0415

    from ...core._stats import contour_levels  # noqa: PLC0415

    values = np.asarray(element.data.grid().values, dtype="float64")
    lv = contour_levels(values, element.levels)
    x0, y0, x1, y1 = element.extent
    ny, nx = values.shape
    tr = QTransform()
    tr.translate(x0, y0)
    tr.scale((x1 - x0) / max(nx - 1, 1), (y1 - y0) / max(ny - 1, 1))
    lut = _pg_lut(element.colormap)
    lo, hi = float(lv[0]), float(lv[-1])
    span = (hi - lo) or 1.0
    items = []
    for v in lv:
        row = lut[int((float(v) - lo) / span * (len(lut) - 1))]
        pen = pg.mkPen(QColor(*(int(c) for c in row[:3])), width=element.line_width)
        # IsocurveItem walks axis 0 as x — our grids are [row=y, col=x], so .T
        item = pg.IsocurveItem(data=values.T, level=float(v), pen=pen)
        item.setTransform(tr)
        ctx.parent_axes.addItem(item)
        items.append(item)
    labels = element.resolved_labels()  # core-placed inline labels ([D117])
    if labels:
        from ...core.encoding import _label_ramp  # noqa: PLC0415

        ramp = _label_ramp(element.colormap)
        bg_pen = pg.mkPen(ctx.theme.background.qt(), width=9.0)
        for lb in labels:
            mx0, my0, mx1, my1 = lb.mask
            mask = pg.PlotCurveItem(x=np.array([mx0, mx1]), y=np.array([my0, my1]),
                                    pen=bg_pen)
            ctx.parent_axes.addItem(mask)
            text = pg.TextItem(lb.text, color=ramp.at(lb.t).qt(),
                               anchor=(0.5, 0.5), angle=lb.angle)  # CCW ([D96])
            text.setPos(lb.x, lb.y)
            ctx.parent_axes.addItem(text)
    return items


def render_errorbars(element: ErrorBars, ctx):
    d = element.data
    x_log, y_log = _xy_log(ctx)
    x, y = _col(d, "x"), _col(d, "y")
    lo, hi, arrows = element.resolved_limits()  # limited sides zeroed ([D116])
    lx, ly = logify(x, x_log), logify(y, y_log)
    kwargs: dict = {}
    if element.direction in ("y", "both"):
        kwargs["bottom"], kwargs["top"] = _log_deltas(y, lo, hi, y_log, ly)
    if element.direction in ("x", "both"):  # ([D92]: direction was unwired)
        kwargs["left"], kwargs["right"] = _log_deltas(x, lo, hi, x_log, lx)
    pen = pg.mkPen(_color(element.color, ctx.theme, ctx.series_index).qt(), width=1.5)
    item = pg.ErrorBarItem(x=lx, y=ly, beam=0.0, pen=pen, **kwargs)
    ctx.parent_axes.addItem(item)
    if arrows is None:
        return item
    items = [item]
    for xs, ys in arrows:  # shafts + heads — the same primitive Quiver uses
        curve = pg.PlotCurveItem(x=logify(xs, x_log), y=logify(ys, y_log),
                                 pen=pen, connect="finite")
        ctx.parent_axes.addItem(curve)
        items.append(curve)
    return items


def render_area(element: Area, ctx):
    """Filled series ([D84b]): zero-baseline `fillLevel` fill, or one band per
    group — layered (overlay) or cumulatively stacked via `FillBetweenItem`.
    Under log-y the zero baseline follows the bar convention (data 1)."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    x_log, y_log = _xy_log(ctx)

    def _band(x, y, sw):
        c = sw.qt()
        c.setAlphaF(element.alpha)
        return pg.PlotDataItem(x=x, y=y, pen=pg.mkPen(sw.qt()), fillLevel=0.0,
                               brush=pg.mkBrush(c))

    if element.by is None:
        item = _band(logify(_col(d, "x"), x_log), logify(_col(d, "y"), y_log),
                     _color(element.color, ctx.theme, ctx.series_index))
        ctx.parent_axes.addItem(item)
        return item
    xs, gs, mat = group_bars(np.asarray(d.series("x")), _col(d, "y"),
                             np.asarray(d.series("by")))
    pos, numeric = _bar_positions(xs)
    if not numeric:
        ctx.parent_axes.getAxis("bottom").setTicks(
            [[(float(i), str(c)) for i, c in enumerate(xs)]])
    lp = logify(pos, x_log)
    swatches = category_swatches(gs, ctx.theme.palette)
    items = []
    bases = np.zeros(len(xs))
    for gi in range(len(gs)):
        if element.mode == "stacked":
            tops = bases + mat[gi]
            lo = pg.PlotDataItem(lp, logify(bases, y_log) if y_log else bases)
            hi = pg.PlotDataItem(lp, logify(tops, y_log))
            c = swatches[gi].qt()
            c.setAlphaF(element.alpha)
            fill = pg.FillBetweenItem(lo, hi, brush=pg.mkBrush(c))
            for it in (lo, hi, fill):
                ctx.parent_axes.addItem(it)
            items.append(fill)
            bases = tops
        else:
            item = _band(lp, logify(mat[gi], y_log), swatches[gi])
            ctx.parent_axes.addItem(item)
            items.append(item)
    if ctx.show_legend:
        from ._legend import add_legend  # noqa: PLC0415

        legend = Legend(kind="categorical", title=channel_title(element.by),
                        entries=tuple((str(g), swatches[i]) for i, g in enumerate(gs)))
        add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    return items


def render_ecdf(element: Ecdf, ctx):
    from ...core._stats import ecdf  # noqa: PLC0415

    xs, fr = ecdf(_col(element.data, "value"))
    x_log, y_log = _xy_log(ctx)
    color = _color(element.color, ctx.theme, ctx.series_index).qt()
    color.setAlphaF(element.alpha)
    item = pg.PlotCurveItem(
        x=logify(xs, x_log), y=logify(fr, y_log), stepMode="left",  # post-step
        pen=pg.mkPen(color, width=element.line_width), connect="finite",
    )
    ctx.parent_axes.addItem(item)
    return item


def render_spread(element: Spread, ctx):
    d = element.data
    x_log, y_log = _xy_log(ctx)
    if element.orient == "h":  # ([D99]) band spans x as a function of y
        y = logify(_col(d, "y"), y_log)
        lo = pg.PlotDataItem(logify(_col(d, "x_lo"), x_log), y)
        hi = pg.PlotDataItem(logify(_col(d, "x_hi"), x_log), y)
    else:
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





_ANCHOR_H = {"center": 0.5, "left": 0.0, "right": 1.0}
_ANCHOR_V = {"center": 0.5, "top": 0.0, "bottom": 1.0}






def _dist_prep(element, ctx):
    """Shared BoxPlot/Violin prep ([D67]): per-category value groups, base
    positions, palette swatches (category order = color_by rule), tick labels,
    and the categorical legend when `by` is set."""
    from ...core._stats import split_by  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    cats, groups = split_by(d.series("value"),
                            d.series("by") if element.by is not None else None)
    pos = np.arange(len(groups), dtype="float64")
    if cats is not None:
        swatches = category_swatches(cats, ctx.theme.palette)
        ctx.parent_axes.getAxis("bottom").setTicks(
            [[(float(i), str(c)) for i, c in enumerate(cats)]]
        )
        if ctx.show_legend:
            from ._legend import add_legend  # noqa: PLC0415

            legend = Legend(kind="categorical", title=channel_title(element.by),
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


RENDERERS: dict[type, Any] = {
    Scatter: render_scatter,
    Curve: render_curve,
    Bars: render_bars,
    Histogram: render_histogram,
    Image: render_image,
    Heatmap: render_heatmap,
    ErrorBars: render_errorbars,
    Spread: render_spread,
    BoxPlot: render_boxplot,
    Violin: render_violin,
    Area: render_area,
    Ecdf: render_ecdf,
    Contour: render_contour,
    Mesh: render_mesh,
    # no Pie ([D90]): pg has no pie primitive; negotiation routes around it
}

# Recommended options each renderer above actually consumes (spec §3.4 / [D51]).
# Anything in an element's RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
# Keep in sync with the renderers — the conformance test guards this.
HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker",
                        "color_norm", "label", "axis"}),
    Curve: frozenset({"color", "color_by", "line_width", "line_style", "marker",
                      "marker_every", "step", "alpha", "label", "axis"}),
    Bars: frozenset({"color", "color_by", "by", "mode", "orient",
                     "annotate", "label"}),
    Histogram: frozenset({"bins", "density", "color", "alpha", "label"}),
    # (Image "interpolation" unwired on pg)
    Image: frozenset({"colormap", "norm", "vmin", "vmax", "gamma", "linthresh", "levels"}),
    Heatmap: frozenset({"colormap", "aggregator", "norm", "vmin", "vmax", "gamma", "linthresh",
                       "levels", "annotate"}),
    ErrorBars: frozenset({"color", "direction", "label", "lo_limit", "hi_limit"}),
    Spread: frozenset({"color", "alpha", "label"}),
    BoxPlot: frozenset({"by", "color", "alpha", "label"}),
    Violin: frozenset({"by", "color", "alpha", "label"}),
    Area: frozenset({"by", "mode", "color", "alpha", "label"}),
    Ecdf: frozenset({"color", "line_width", "alpha", "label"}),
    Contour: frozenset({"levels", "colormap", "line_width", "label", "annotate"}),  # not filled
    Mesh: frozenset({"colormap", "norm", "vmin", "vmax", "gamma", "linthresh", "levels"}),
}
