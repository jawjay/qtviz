"""matplotlib element renderers (spec §4.2).

Same Element vocabulary as pyqtgraph, drawn through `Axes`. Each returns the
mpl artist so interaction wiring can reach it.
"""
# mypy: disable-error-code="attr-defined, assignment"
# (post-resolve shape invariant — see the pyqtgraph renderer note)

from __future__ import annotations

from typing import Any

import numpy as np

from ...core.color import Color
from ...elements import (
    Area,
    Arrow,
    Bars,
    BoxPlot,
    Contour,
    Curve,
    Ecdf,
    Ellipse,
    ErrorBars,
    Heatmap,
    Histogram,
    HLine,
    Image,
    Mesh,
    Pie,
    Polygon,
    Quiver,
    Rect,
    RefLine,
    Scatter,
    Span,
    Spread,
    Text,
    Violin,
    VLine,
)

_LINE_STYLE = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}


def _ls(style):
    """Named style or a dash tuple in points ([D99]) → mpl linestyle."""
    return _LINE_STYLE[style] if isinstance(style, str) else (0, style)


# qtviz marker vocabulary → matplotlib marker codes ([D51]/[D99]).
_MARKER = {"circle": "o", "square": "s", "triangle": "^", "triangle_down": "v",
           "diamond": "D", "cross": "X", "plus": "P", "star": "*",
           "pentagon": "p", "hexagon": "h"}
# qtviz step vocabulary → matplotlib drawstyle ([D84]).
_STEP = {"pre": "steps-pre", "mid": "steps-mid", "post": "steps-post"}


def _mpl_cmap(name: str):
    """Case-insensitive colormap resolution with the same warn-fallback
    contract as the other backends (gallery-audit §2: 'greys' raised from
    inside mpl while webengine lowercased — one vocabulary, one behavior)."""
    import matplotlib  # noqa: PLC0415

    registry = matplotlib.colormaps
    if name in registry:
        return registry[name]
    lower = name.lower()
    for known in registry:
        if known.lower() == lower:
            return registry[known]
    import warnings  # noqa: PLC0415

    from ...errors import QtvizWarning  # noqa: PLC0415

    warnings.warn(f"matplotlib: no colormap named {name!r}; using 'viridis'",
                  QtvizWarning, stacklevel=2)
    return registry["viridis"]


def _color(spec, theme, idx: int = 0) -> Color:
    if spec is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(spec)


def _col(ref, name) -> np.ndarray:
    from ...core._time import as_float_seconds  # noqa: PLC0415

    return as_float_seconds(ref.series(name))  # datetime64 → epoch s ([D94])


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
        norm=getattr(element, "color_norm", "linear"),
    )


def render_scatter(element: Scatter, ctx):
    d = element.data
    s = _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6) ** 2
    marker = _MARKER[element.marker]
    if element.color_by is not None:
        rgba, legend = _color_mapping(element, d, ctx.theme)
        artist = ctx.parent_axes.scatter(
            _col(d, "x"), _col(d, "y"), c=rgba, s=s, alpha=element.alpha, marker=marker,
            rasterized=element.matplotlib_rasterized,
        )
        if ctx.show_legend:
            _add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
        return artist
    return ctx.parent_axes.scatter(
        _col(d, "x"), _col(d, "y"),
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
        s=s, alpha=element.alpha, marker=marker,
        rasterized=element.matplotlib_rasterized,
    )


# `legend_position` vocabulary → mpl `loc` (None → mpl's default placement).
_LOC = {"auto": None, "right": "upper right", "top": "upper center"}


def _draw_key(ax, handles, title, fg, position: str) -> None:
    """(Re)draw the axes key legend from `handles`, remembering them so the Overlay
    aggregation ([D60]) can merge its labeled entries in rather than replacing a
    color-mapping key."""
    ax._qtviz_handles = handles
    loc = _LOC.get(position)
    kw = {"loc": loc} if loc is not None else {}
    if any(isinstance(h, _ArrowKeyHandle) for h in handles):
        kw["handler_map"] = {_ArrowKeyHandle: _ArrowKeyHandler()}
    ax.legend(handles=handles, title=title, fontsize=8, framealpha=0.85, labelcolor=fg, **kw)


class _ArrowKeyHandle:
    """Proxy legend handle for the Quiver reference key ([D112])."""

    def __init__(self, entry) -> None:
        self.entry = entry

    def get_label(self):
        return self.entry.label


class _ArrowKeyHandler:
    """Legend handler drawing the core unit-arrow sample (`arrow_key_points`,
    same ±25° barbs as the field) into the handle box."""

    def legend_artist(self, legend, orig_handle, fontsize, handlebox):
        from matplotlib.lines import Line2D  # noqa: PLC0415

        from ...core._geometry import arrow_key_points  # noqa: PLC0415

        e = orig_handle.entry
        shaft, head = arrow_key_points(e.head_scale)
        x0, y0 = handlebox.xdescent, handlebox.ydescent
        w, mid = handlebox.width, handlebox.height / 2.0
        color = e.swatch.mpl()
        artists = [
            Line2D(x0 + pts[:, 0] * w, y0 + mid + pts[:, 1] * w,
                   color=color, linewidth=max(e.line_width, 1.0))
            for pts in (shaft, head)
        ]
        for a in artists:
            a.set_transform(handlebox.get_transform())
            handlebox.add_artist(a)
        return artists[0]


def append_legend_entries(ax, entries, theme, position: str = "auto") -> None:
    """Merge the Overlay-aggregated `LegendEntry` contributions into the axes
    legend (after any color-mapping key drawn by a `color_by` renderer). An
    `"arrow"` glyph (the [D112] Quiver key) draws the core unit-arrow sample
    via a custom handler instead of a color patch."""
    from matplotlib.patches import Patch  # noqa: PLC0415

    handles = list(getattr(ax, "_qtviz_handles", []))
    handles += [
        _ArrowKeyHandle(e) if getattr(e, "glyph", "swatch") == "arrow"
        else Patch(facecolor=e.swatch.mpl(), label=e.label)
        for e in entries
    ]
    prev = ax.get_legend()
    title = prev.get_title().get_text() or None if prev is not None else None
    _draw_key(ax, handles, title, theme.foreground.mpl(), position)


def _add_legend(ax, legend, theme, position: str = "auto") -> None:
    from matplotlib.patches import Patch  # noqa: PLC0415

    fg = theme.foreground.mpl()
    prev = getattr(ax, "_qtviz_cbar", None)
    if prev is not None:  # remove a prior colorbar so re-aggregation refreshes, not stacks (C3)
        prev.remove()
        ax._qtviz_cbar = None
    if legend.kind == "categorical":
        handles = [Patch(facecolor=c.mpl(), label=label) for label, c in legend.entries]
        _draw_key(ax, handles, legend.title, fg, position)
    elif not legend.linear:  # non-linear density: endpoints-only key, not a misleading bar ([D48])
        ramp = legend.ramp
        handles = [Patch(facecolor=ramp[-1].mpl(), label=f"{legend.vmax:.3g}"),
                   Patch(facecolor=ramp[0].mpl(), label=f"{legend.vmin:.3g}")]
        _draw_key(ax, handles, legend.title, fg, position)
    else:
        from matplotlib.cm import ScalarMappable  # noqa: PLC0415
        from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: PLC0415

        cmap = LinearSegmentedColormap.from_list("qtviz", [c.mpl() for c in legend.ramp])
        sm = ScalarMappable(norm=Normalize(legend.vmin, legend.vmax), cmap=cmap)
        bar = ax.figure.colorbar(sm, ax=ax)
        ax._qtviz_cbar = bar
        if legend.title:
            bar.set_label(legend.title, color=fg)
        bar.ax.tick_params(colors=fg)


def _curve_color_by(element: Curve, ctx):
    """Per-point Curve coloring ([D100]): categorical → the shared core split
    into per-category sub-lines; continuous → a LineCollection colored per
    segment through the same `map_colors` ramp as everything else."""
    from ...core._stats import categorical_line_split  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches, is_categorical  # noqa: PLC0415

    d = element.data
    ax = ctx.parent_axes
    x, y = _col(d, "x"), _col(d, "y")
    values = np.asarray(d.series("color"))
    if is_categorical(values):
        cats, parts = categorical_line_split(x, y, values)
        swatches = category_swatches(cats, ctx.theme.palette)
        lines = []
        for (xs, ys), sw in zip(parts, swatches, strict=True):
            (line,) = ax.plot(xs, ys, color=sw.mpl(), lw=element.line_width,
                              ls=_ls(element.line_style), alpha=element.alpha)
            lines.append(line)
        if ctx.show_legend:
            legend = Legend(kind="categorical", title=element.color_by,
                            entries=tuple((str(c), sw)
                                          for c, sw in zip(cats, swatches, strict=True)))
            _add_legend(ax, legend, ctx.theme, ctx.legend_position)
        return lines
    from matplotlib.collections import LineCollection  # noqa: PLC0415

    rgba, legend = _color_mapping(element, d, ctx.theme)
    pts = np.column_stack([x, y]).reshape(-1, 1, 2)
    segments = np.concatenate([pts[:-1], pts[1:]], axis=1)
    lc = LineCollection(list(segments), colors=rgba[:-1],
                        linewidths=element.line_width, alpha=element.alpha)
    ax.add_collection(lc)
    ax.autoscale_view()
    if ctx.show_legend:
        _add_legend(ax, legend, ctx.theme, ctx.legend_position)
    return lc


def render_curve(element: Curve, ctx):
    if element.color_by is not None:
        return _curve_color_by(element, ctx)
    (line,) = ctx.parent_axes.plot(
        _col(element.data, "x"), _col(element.data, "y"),
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
        lw=element.line_width, ls=_ls(element.line_style), alpha=element.alpha,
        drawstyle=_STEP[element.step] if element.step else "default",
        marker=_MARKER[element.marker] if element.marker else None, markersize=6,
        markevery=element.marker_every if element.marker_every > 1 else None,
    )
    return line


def _bar_fns(ax, orient: str):
    """The axis-swapped trio for one bar orientation ([D85]): the draw call
    (`bar`/`barh` — both take (positions, lengths) positionally), the kwarg
    naming the bar *thickness*, and the categorical tick setter."""
    if orient == "h":
        return ax.barh, "height", ax.set_yticks
    return ax.bar, "width", ax.set_xticks


def _label_bars(ax, container, element, theme, *, inside: bool = False) -> None:
    """Value labels on one bar container ([D98]) — formatted through the
    [D86] tick vocabulary ("auto" → '%g')."""
    if element.bar_labels is None:
        return
    from ...core._ticks import format_tick  # noqa: PLC0415

    spec = element.bar_labels if element.bar_labels != "auto" else "g"
    ax.bar_label(container, fmt=lambda v: format_tick(v, spec),
                 color=theme.foreground.mpl(), padding=2,
                 label_type="center" if inside else "edge", fontsize=8)


def render_bars(element: Bars, ctx):
    if element.group is not None:
        return _render_group_bars(element, ctx)
    height = _col(element.data, "y")
    try:
        x = _col(element.data, "x")
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")
    bar, thick, _ticks = _bar_fns(ctx.parent_axes, element.orient)
    if element.color_by is not None:  # per-bar colors ([D100])
        rgba, legend = _color_mapping(element, element.data, ctx.theme)
        container = bar(x, height, **{thick: 0.8}, color=list(rgba))
        if ctx.show_legend:
            _add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
    else:
        container = bar(x, height, **{thick: 0.8},
                        color=_color(element.color, ctx.theme, ctx.series_index).mpl())
    _label_bars(ctx.parent_axes, container, element, ctx.theme)
    return container


def _render_group_bars(element: Bars, ctx):
    """One bar series per group ([D68]) — offset (grouped) or base-stacked, in
    either orientation ([D85]); palette per group in category order + a
    categorical group legend."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    xs, gs, mat = group_bars(np.asarray(d.series("x")), _col(d, "y"),
                             np.asarray(d.series("group")))
    numeric = np.issubdtype(xs.dtype, np.number)
    pos = xs.astype("float64") if numeric else np.arange(len(xs), dtype="float64")
    ax = ctx.parent_axes
    bar, thick, set_ticks = _bar_fns(ax, element.orient)
    base_kw = "left" if element.orient == "h" else "bottom"
    if not numeric:
        set_ticks(pos, [str(c) for c in xs])
    swatches = category_swatches(gs, ctx.theme.palette)
    artists = []
    if element.mode == "grouped":
        total_w = 0.8
        w = total_w / len(gs)
        for gi in range(len(gs)):
            artists.append(bar(pos - total_w / 2 + w / 2 + gi * w, mat[gi],
                               **{thick: w * 0.95}, color=swatches[gi].mpl()))
            _label_bars(ax, artists[-1], element, ctx.theme)
    else:  # stacked
        bases = np.zeros(len(xs))
        for gi in range(len(gs)):
            artists.append(bar(pos, mat[gi], **{thick: 0.6, base_kw: bases},
                               color=swatches[gi].mpl()))
            _label_bars(ax, artists[-1], element, ctx.theme, inside=True)
            bases = bases + mat[gi]
    if ctx.show_legend:
        legend = Legend(kind="categorical", title=element.group,
                        entries=tuple((str(g), swatches[i]) for i, g in enumerate(gs)))
        _add_legend(ax, legend, ctx.theme, ctx.legend_position)
    return artists


def render_histogram(element: Histogram, ctx):
    from ...core._stats import histogram  # noqa: PLC0415

    counts, edges = histogram(_col(element.data, "column"), element.bins,
                              density=element.density)  # shared binning ([D93])
    return ctx.parent_axes.bar(
        edges[:-1], counts, width=np.diff(edges), align="edge",
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
        alpha=element.alpha,
    )


def render_image(element: Image, ctx):
    x0, y0, x1, y1 = element.bounds
    agg = getattr(element, "_raster_agg", None)
    if agg is not None:  # datashaded raster: shade + legend with the View's Theme (C2/C3)
        result = _shade_raster(element, agg, ctx.theme)
        artist = ctx.parent_axes.imshow(
            result.rgba, extent=(x0, x1, y0, y1), origin="lower", aspect="auto",
        )
        if result.legend is not None and ctx.show_legend:
            # category key / colorbar (C3)
            _add_legend(ctx.parent_axes, result.legend, ctx.theme, ctx.legend_position)
        _wire_dynamic_raster(element, artist, ctx)
        return artist
    if getattr(element, "_grid_source", None) is not None:
        # decimated lazy grid ([D74]) — shaded like the regrid loop ([D75])
        from ...core.palette import palettes  # noqa: PLC0415
        from ...data.regrid import shade_values  # noqa: PLC0415

        rgba, legend = shade_values(element.data.grid().values, palettes.get("viridis"))
        artist = ctx.parent_axes.imshow(
            rgba, extent=(x0, x1, y0, y1), origin="lower", aspect="auto",
        )
        if ctx.show_legend:
            _add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
        _wire_dynamic_regrid(element, artist, ctx)
        return artist
    values = np.asarray(element.data.grid().values)
    if values.ndim == 3:  # RGBA raster (e.g. a user-built image)
        artist = ctx.parent_axes.imshow(
            values, extent=(x0, x1, y0, y1), origin="lower", aspect="auto",
            interpolation=element.interpolation,
        )
        _wire_dynamic_raster(element, artist, ctx)
        return artist
    display, norm_kw = _norm_display(  # ([D105])
        element, np.asarray(values, dtype="float64"), ctx, ctx.parent_axes)
    return ctx.parent_axes.imshow(
        display, extent=(x0, x1, y0, y1), origin="lower", aspect="auto",
        cmap=_mpl_cmap(element.colormap), interpolation=element.interpolation,
        **norm_kw,
    )


def _shade_raster(element, aggregate, theme):
    """Shade a datashader `Aggregate` with the View's `Theme` into rgba + a `Legend`
    (categorical key from `theme.palette`, continuous ramp from viridis) so a raster
    matches a native `color_by` (C2/C3, [D50])."""
    from ...core.palette import palettes  # noqa: PLC0415
    from ...ext.datashader import shade_aggregate  # noqa: PLC0415

    return shade_aggregate(
        aggregate, palette=theme.palette, continuous_palette=palettes.get("viridis"),
        title=_raster_title(element),
    )


def _raster_title(element) -> str | None:
    """Legend title for a datashaded raster — the source's `color_by` column, or
    `None` (→ a bare density `count` is labeled "density")."""
    return getattr(getattr(element, "_raster_source", None), "color_by", None)


def _wire_dynamic_raster(element, artist, ctx) -> None:
    """If this Image came from a datashaded Scatter/Curve, re-aggregate the source
    to the viewport on pan/zoom (4b) and emit the aggregated value under the cursor
    on hover ([D46]). Both are parked on the Axes so the RenderHandle disposes them."""
    source = getattr(element, "_raster_source", None)
    if source is None:
        return
    from types import SimpleNamespace  # noqa: PLC0415

    from ...core.palette import palettes  # noqa: PLC0415
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...ext.datashader import themed_rasterize  # noqa: PLC0415
    from ._raster import MplRasterTarget, wire_raster_hover  # noqa: PLC0415

    ax = ctx.parent_axes
    theme = ctx.theme
    position = ctx.legend_position
    holder = SimpleNamespace(aggregate=getattr(element, "_raster_aggregate", None))
    target = MplRasterTarget(artist, ax)
    refresh_legend = (  # refresh on re-aggregation (C3); a suppressed legend stays off
        (lambda lg: _add_legend(ax, lg, theme, position)) if ctx.show_legend
        else (lambda lg: None)
    )
    controller = RasterController(
        source=source, target=target,
        rasterize=themed_rasterize(theme.palette, palettes.get("viridis"), _raster_title(element)),
        parent=ax.figure.canvas,
        on_aggregate=lambda agg: setattr(holder, "aggregate", agg),
        on_legend=refresh_legend,
    )
    controller.element_id = element.id  # streaming refresh routes by id ([D77])
    if not hasattr(ax, "_qtviz_rasters"):
        ax._qtviz_rasters = []
    ax._qtviz_rasters.append(controller)
    ax._qtviz_rasters.append(wire_raster_hover(ax, element.id, ctx.event_bus, holder))



def _wire_dynamic_regrid(element, artist, ctx) -> None:
    """Viewport-regrid loop for a decimated lazy grid ([D75]) — mirrors the
    pyqtgraph wiring through the shared RasterController."""
    source = getattr(element, "_grid_source", None)
    if source is None:
        return
    from ...core.palette import palettes  # noqa: PLC0415
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...data.regrid import make_regrid  # noqa: PLC0415
    from ._raster import MplRasterTarget  # noqa: PLC0415

    ax = ctx.parent_axes
    theme = ctx.theme
    position = ctx.legend_position
    refresh_legend = (
        (lambda lg: _add_legend(ax, lg, theme, position)) if ctx.show_legend
        else (lambda lg: None)
    )
    controller = RasterController(
        source=source, target=MplRasterTarget(artist, ax),
        rasterize=make_regrid(element.bounds, palettes.get("viridis")),
        parent=ax.figure.canvas, on_legend=refresh_legend,
    )
    if not hasattr(ax, "_qtviz_rasters"):
        ax._qtviz_rasters = []
    ax._qtviz_rasters.append(controller)


def _heat_extent(ax, centers, axis: str) -> tuple[float, float]:
    """Data-space extent for one heatmap axis ([D92]): numeric centers place the
    cells at their values; categorical centers use index positions + tick labels."""
    from ...core._stats import cell_extent  # noqa: PLC0415

    arr = np.asarray(centers)
    if np.issubdtype(arr.dtype, np.number):
        return cell_extent(arr)
    n = len(arr)
    (ax.set_xticks if axis == "x" else ax.set_yticks)(
        np.arange(n), [str(c) for c in arr])
    return (-0.5, n - 0.5)


def _norm_display(element, values, ctx, ax):
    """[D105]: normalize in core when the norm surface is engaged; a colorbar
    with denormalized tick labels (honest — the analytic inverse) appears
    only then, so plain rasters keep their exact pre-[D105] look. Returns
    `(display_values, imshow_kwargs)`."""
    from ...core.encoding import denormalize, norm_engaged, normalize_values  # noqa: PLC0415

    if not norm_engaged(element):
        return values, {}
    normed, lo, hi = normalize_values(values, norm=element.norm, vmin=element.vmin,
                                      vmax=element.vmax, gamma=element.gamma)
    if ctx.show_legend:
        from matplotlib.cm import ScalarMappable  # noqa: PLC0415
        from matplotlib.colors import Normalize  # noqa: PLC0415
        from matplotlib.ticker import FuncFormatter  # noqa: PLC0415

        sm = ScalarMappable(norm=Normalize(0.0, 1.0), cmap=_mpl_cmap(element.colormap))
        bar = ax.figure.colorbar(sm, ax=ax)
        bar.ax.yaxis.set_major_formatter(FuncFormatter(
            lambda t, _p: format(denormalize(t, lo, hi, element.norm, element.gamma), "g")))
        bar.ax.tick_params(colors=ctx.theme.foreground.mpl())
    return normed, {"vmin": 0.0, "vmax": 1.0}


def render_heatmap(element: Heatmap, ctx):
    from ...core._stats import grid_reduce  # noqa: PLC0415

    d = element.data
    xs, ys, grid = grid_reduce(d.series("x"), d.series("y"), _col(d, "z"),
                               element.aggregator)  # real reduction ([D69])
    ax = ctx.parent_axes
    x0, x1 = _heat_extent(ax, xs, "x")
    y0, y1 = _heat_extent(ax, ys, "y")
    labels = element.resolved_cell_labels(xs, ys, grid, ctx.theme)  # pre-norm grid ([D113])
    grid, norm_kw = _norm_display(element, grid, ctx, ax)  # ([D105])
    artist = ax.imshow(grid, origin="lower", aspect="auto",
                       cmap=_mpl_cmap(element.colormap), extent=(x0, x1, y0, y1),
                       **norm_kw)
    for lb in labels:
        ax.text(lb.x, lb.y, lb.text, color=lb.color.mpl(),
                ha="center", va="center", fontsize=8)
    return artist


def render_area(element: Area, ctx):
    """Filled series ([D84b]): zero-baseline fill, or one band per group —
    layered (overlay) or cumulatively stacked."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    ax = ctx.parent_axes
    if element.group is None:
        return ax.fill_between(
            _col(d, "x"), 0.0, _col(d, "y"),
            color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
            alpha=element.alpha,
        )
    xs, gs, mat = group_bars(np.asarray(d.series("x")), _col(d, "y"),
                             np.asarray(d.series("group")))
    numeric = np.issubdtype(xs.dtype, np.number)
    pos = xs.astype("float64") if numeric else np.arange(len(xs), dtype="float64")
    if not numeric:
        ax.set_xticks(pos, [str(c) for c in xs])
    swatches = category_swatches(gs, ctx.theme.palette)
    artists = []
    bases = np.zeros(len(xs))
    for gi in range(len(gs)):
        top = bases + mat[gi] if element.mode == "stacked" else mat[gi]
        artists.append(ax.fill_between(pos, bases, top, color=swatches[gi].mpl(),
                                       alpha=element.alpha))
        if element.mode == "stacked":
            bases = top
    if ctx.show_legend:
        legend = Legend(kind="categorical", title=element.group,
                        entries=tuple((str(g), swatches[i]) for i, g in enumerate(gs)))
        _add_legend(ax, legend, ctx.theme, ctx.legend_position)
    return artists


def render_ecdf(element: Ecdf, ctx):
    from ...core._stats import ecdf  # noqa: PLC0415

    xs, fr = ecdf(_col(element.data, "column"))
    (line,) = ctx.parent_axes.plot(
        xs, fr, color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
        lw=element.line_width, alpha=element.alpha, drawstyle="steps-post",
    )
    return line


def render_pie(element: Pie, ctx):
    d = element.data
    vals = _col(d, "values")
    labels = ([str(v) for v in np.asarray(d.series("labels"))]
              if element.labels is not None else None)
    palette = ctx.theme.palette
    ax = ctx.parent_axes
    ax.set_axis_off()  # wedges have no axes; the surface title still draws
    wedgeprops = {"alpha": element.alpha}
    if element.hole:
        wedgeprops["width"] = 1.0 - element.hole  # annular wedges → donut
    wedges, _texts = ax.pie(
        vals, labels=labels,
        colors=[palette[i % len(palette)].mpl() for i in range(len(vals))],
        wedgeprops=wedgeprops, textprops={"color": ctx.theme.foreground.mpl()},
    )
    return wedges


def render_quiver(element: Quiver, ctx):
    """Vector field ([D107]) from the shared core geometry — two polylines,
    identical on every backend (no native `quiver`: one geometry, one meaning)."""
    (sx, sy), (hx, hy) = element.resolved_segments()
    color = _color(element.color, ctx.theme, ctx.series_index).mpl()
    (shafts,) = ctx.parent_axes.plot(sx, sy, color=color, lw=element.line_width,
                                     alpha=element.alpha)
    (heads,) = ctx.parent_axes.plot(hx, hy, color=color, lw=element.line_width,
                                    alpha=element.alpha)
    return [shafts, heads]


def render_mesh(element: Mesh, ctx):
    """Non-uniform rectilinear grid ([D106]) — edges straight to pcolormesh;
    the [D105] norm surface shared with Image/Heatmap."""
    values = element.check_shape(element.data.grid().values)
    display, norm_kw = _norm_display(element, values, ctx, ctx.parent_axes)
    return ctx.parent_axes.pcolormesh(
        np.asarray(element.x_edges), np.asarray(element.y_edges), display,
        cmap=_mpl_cmap(element.colormap), **norm_kw)


def render_contour(element: Contour, ctx):
    """Iso-lines / filled bands over a grid ([D89]) — level values come from
    core (`contour_levels`) so every backend draws the same lines."""
    from ...core._stats import contour_levels  # noqa: PLC0415

    values = np.asarray(element.data.grid().values, dtype="float64")
    lv = contour_levels(values, element.levels)
    x0, y0, x1, y1 = element.bounds
    ax = ctx.parent_axes
    if element.filled:
        cs = ax.contourf(values, levels=lv, extent=(x0, x1, y0, y1),
                         origin="lower", cmap=_mpl_cmap(element.colormap),
                         extend="both")
        if ctx.show_legend:
            bar = ax.figure.colorbar(cs, ax=ax)
            bar.ax.tick_params(colors=ctx.theme.foreground.mpl())
        return cs
    return ax.contour(values, levels=lv, extent=(x0, x1, y0, y1), origin="lower",
                      cmap=_mpl_cmap(element.colormap), linewidths=element.line_width)


def render_errorbars(element: ErrorBars, ctx):
    d = element.data
    lo, hi = _col(d, "err_lo"), _col(d, "err_hi")
    err = np.vstack([lo, hi])  # [below, above]
    kwargs = {}
    if element.direction in ("y", "both"):
        kwargs["yerr"] = err
    if element.direction in ("x", "both"):
        kwargs["xerr"] = err
    return ctx.parent_axes.errorbar(
        _col(d, "x"), _col(d, "y"), fmt="o",
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(), **kwargs,
    )


def render_spread(element: Spread, ctx):
    d = element.data
    color = _color(element.color, ctx.theme, ctx.series_index).mpl()
    if element.orient == "h":  # ([D99]) band spans x as a function of y
        return ctx.parent_axes.fill_betweenx(
            _col(d, "y"), _col(d, "x_lo"), _col(d, "x_hi"),
            color=color, alpha=element.alpha,
        )
    return ctx.parent_axes.fill_between(
        _col(d, "x"), _col(d, "y_lo"), _col(d, "y_hi"),
        color=color, alpha=element.alpha,
    )


def _ref_color(spec, theme) -> Color:
    """Annotation default: the theme foreground — chrome, not a palette series."""
    return Color(spec) if spec is not None else theme.foreground


def render_hline(element: HLine, ctx):
    return ctx.parent_axes.axhline(
        element.y, color=_ref_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_ls(element.line_style), alpha=element.alpha,
    )


def render_vline(element: VLine, ctx):
    return ctx.parent_axes.axvline(
        element.x, color=_ref_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_ls(element.line_style), alpha=element.alpha,
    )


def render_span(element: Span, ctx):
    fn = ctx.parent_axes.axhspan if element.orient == "h" else ctx.parent_axes.axvspan
    return fn(element.lo, element.hi,
              color=_ref_color(element.color, ctx.theme).mpl(), alpha=element.alpha)


_VA = {"center": "center", "top": "top", "bottom": "bottom"}


def render_text(element: Text, ctx):
    fg = _ref_color(element.color, ctx.theme).mpl()
    kwargs = {"color": fg, "ha": element.anchor, "va": _VA[element.anchor_v],
              "rotation": element.rotation, "rotation_mode": "anchor"}
    if element.size is not None:
        kwargs["fontsize"] = element.size
    if element.frame:
        kwargs["bbox"] = {"boxstyle": "round,pad=0.35",
                          "facecolor": ctx.theme.background.mpl(), "edgecolor": fg}
    return ctx.parent_axes.text(element.x, element.y, element.text, **kwargs)


# Arrow head vocabulary → mpl arrowstyle ([D96]).
_ARROWSTYLE = {"end": "-|>", "both": "<|-|>", "none": "-"}


def _refline_scales_ok(ctx, backend: str) -> bool:
    if ctx.x_scale in ("log", "symlog") or ctx.y_scale in ("log", "symlog"):
        import warnings  # noqa: PLC0415

        from ...errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(f"{backend}: RefLine is a straight data-space line and has "
                      "no log-scale form; it was dropped.", QtvizWarning, stacklevel=2)
        return False
    return True


def render_refline(element, ctx):
    if not _refline_scales_ok(ctx, "matplotlib"):
        return None
    return ctx.parent_axes.axline(
        (0.0, element.intercept), slope=element.slope,
        color=_ref_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_ls(element.line_style), alpha=element.alpha,
    )


def render_arrow(element: Arrow, ctx):
    color = _ref_color(element.color, ctx.theme).mpl()
    return ctx.parent_axes.annotate(
        "", xy=(element.x1, element.y1), xytext=(element.x0, element.y0),
        arrowprops={"arrowstyle": _ARROWSTYLE[element.head], "color": color,
                    "lw": element.line_width, "alpha": element.alpha,
                    "shrinkA": 0, "shrinkB": 0},
        annotation_clip=False,
    )


def _shape_style(element, ctx) -> dict:
    color = _ref_color(element.color, ctx.theme).mpl()
    return {"edgecolor": color, "linewidth": element.line_width,
            "alpha": element.alpha,
            "facecolor": color if element.fill else "none"}


def render_rect(element: Rect, ctx):
    from matplotlib import patches  # noqa: PLC0415

    patch = patches.Rectangle((element.x0, element.y0),
                              element.x1 - element.x0, element.y1 - element.y0,
                              **_shape_style(element, ctx))
    ctx.parent_axes.add_patch(patch)
    return patch


def render_ellipse(element: Ellipse, ctx):
    from matplotlib import patches  # noqa: PLC0415

    patch = patches.Ellipse((element.cx, element.cy), 2 * element.rx, 2 * element.ry,
                            angle=element.angle, **_shape_style(element, ctx))
    ctx.parent_axes.add_patch(patch)
    return patch


def render_polygon(element: Polygon, ctx):
    from matplotlib import patches  # noqa: PLC0415

    patch = patches.Polygon(np.asarray(element.points), closed=True,
                            **_shape_style(element, ctx))
    ctx.parent_axes.add_patch(patch)
    return patch




def _dist_prep(element, ctx):
    """Shared BoxPlot/Violin prep ([D67]) — mirrors the pyqtgraph helper."""
    from ...core._stats import split_by  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    cats, groups = split_by(d.series("column"),
                            d.series("by") if element.by is not None else None)
    pos = np.arange(len(groups), dtype="float64")
    ax = ctx.parent_axes
    if cats is not None:
        swatches = category_swatches(cats, ctx.theme.palette)
        if ctx.show_legend:
            legend = Legend(kind="categorical", title=element.by,
                            entries=tuple((str(c), swatches[i]) for i, c in enumerate(cats)))
            _add_legend(ax, legend, ctx.theme, ctx.legend_position)
    else:
        swatches = [_color(element.color, ctx.theme, ctx.series_index)] * len(groups)
    return groups, pos, swatches, cats


def _dist_ticks(ax, pos, cats) -> None:
    """Category tick labels — applied *after* drawing (`ax.bxp` overwrites any
    labels set before it)."""
    if cats is not None:
        ax.set_xticks(pos, [str(c) for c in cats])


def render_boxplot(element: BoxPlot, ctx):
    """`ax.bxp` with the shared precomputed `box_stats` ([D67]) — matplotlib
    draws, qtviz decides the statistics."""
    from ...core._stats import box_stats  # noqa: PLC0415

    groups, pos, swatches, cats = _dist_prep(element, ctx)
    stats = [box_stats(g) for g in groups]
    bxp = [{"med": s.median, "q1": s.q1, "q3": s.q3, "whislo": s.lo_whisker,
            "whishi": s.hi_whisker, "fliers": s.outliers} for s in stats]
    result = ctx.parent_axes.bxp(bxp, positions=pos, showfliers=True, patch_artist=True)
    for patch, sw in zip(result["boxes"], swatches, strict=True):
        patch.set_facecolor(sw.mpl())
        patch.set_alpha(element.alpha)
    _dist_ticks(ctx.parent_axes, pos, cats)
    return result


def render_violin(element: Violin, ctx):
    """Silhouettes from the shared `kde` ([D67]) via `fill_betweenx`."""
    from ...core._stats import kde  # noqa: PLC0415

    groups, pos, swatches, cats = _dist_prep(element, ctx)
    artists = []
    for i, g in enumerate(groups):
        grid, dens = kde(g)
        half = dens / (dens.max() or 1.0) * 0.4
        artists.append(ctx.parent_axes.fill_betweenx(
            grid, pos[i] - half, pos[i] + half,
            color=swatches[i].mpl(), alpha=element.alpha,
        ))
    _dist_ticks(ctx.parent_axes, pos, cats)
    return artists


RENDERERS: dict[type, Any] = {
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
    Area: render_area,
    Ecdf: render_ecdf,
    Pie: render_pie,
    Contour: render_contour,
    Mesh: render_mesh,
    Quiver: render_quiver,
    Arrow: render_arrow,
    Rect: render_rect,
    Ellipse: render_ellipse,
    Polygon: render_polygon,
    RefLine: render_refline,
}

# Recommended options each renderer above actually consumes (spec §3.4 / [D51]).
# Anything in an element's RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
# Keep in sync with the renderers — the conformance test guards this.


HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker",
                        "color_norm", "label", "axis"}),
    Curve: frozenset({"color", "color_by", "line_width", "line_style", "marker",
                      "marker_every", "step", "alpha", "label", "axis"}),
    Bars: frozenset({"color", "color_by", "group", "mode", "orient",
                     "bar_labels", "label"}),
    Histogram: frozenset({"bins", "density", "color", "alpha", "label"}),
    Image: frozenset({"colormap", "interpolation", "norm", "vmin", "vmax", "gamma"}),
    Heatmap: frozenset({"colormap", "aggregator", "norm", "vmin", "vmax", "gamma", "cell_labels"}),
    ErrorBars: frozenset({"direction", "color", "label"}),
    Spread: frozenset({"color", "alpha", "label"}),
    HLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    VLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Span: frozenset({"color", "alpha", "label"}),
    Text: frozenset({"color", "size", "anchor", "anchor_v", "rotation", "frame"}),
    Arrow: frozenset({"head", "color", "line_width", "alpha", "label"}),
    Rect: frozenset({"color", "line_width", "alpha", "fill", "label"}),
    Ellipse: frozenset({"color", "line_width", "alpha", "fill", "label"}),
    Polygon: frozenset({"color", "line_width", "alpha", "fill", "label"}),
    BoxPlot: frozenset({"by", "color", "alpha", "label"}),
    Violin: frozenset({"by", "color", "alpha", "label"}),
    Area: frozenset({"group", "mode", "color", "alpha", "label"}),
    Ecdf: frozenset({"color", "line_width", "alpha", "label"}),
    Pie: frozenset({"labels", "hole", "alpha"}),
    Contour: frozenset({"levels", "filled", "colormap", "line_width", "label"}),
    Mesh: frozenset({"colormap", "norm", "vmin", "vmax", "gamma"}),
    Quiver: frozenset({"arrow_scale", "head_scale", "color", "line_width",
                       "alpha", "label", "key", "key_label"}),
    RefLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
}
