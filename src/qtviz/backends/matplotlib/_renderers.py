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
    HLine,
    Image,
    Scatter,
    Span,
    Spread,
    Text,
    VLine,
)

_LINE_STYLE = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}
# qtviz marker vocabulary → matplotlib marker codes ([D51]).
_MARKER = {"circle": "o", "square": "s", "triangle": "^", "diamond": "D", "cross": "X"}


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
    marker = _MARKER[element.marker]
    if element.color_by is not None:
        rgba, legend = _color_mapping(element, d, ctx.theme)
        artist = ctx.parent_axes.scatter(
            _col(d, "x"), _col(d, "y"), c=rgba, s=s, alpha=element.alpha, marker=marker,
        )
        if ctx.show_legend:
            _add_legend(ctx.parent_axes, legend, ctx.theme, ctx.legend_position)
        return artist
    return ctx.parent_axes.scatter(
        _col(d, "x"), _col(d, "y"),
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
        s=s, alpha=element.alpha, marker=marker,
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
    ax.legend(handles=handles, title=title, fontsize=8, framealpha=0.85, labelcolor=fg, **kw)


def append_legend_entries(ax, entries, theme, position: str = "auto") -> None:
    """Merge the Overlay-aggregated `LegendEntry` contributions into the axes
    legend (after any color-mapping key drawn by a `color_by` renderer)."""
    from matplotlib.patches import Patch  # noqa: PLC0415

    handles = list(getattr(ax, "_qtviz_handles", []))
    handles += [Patch(facecolor=e.swatch.mpl(), label=e.label) for e in entries]
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


def render_curve(element: Curve, ctx):
    (line,) = ctx.parent_axes.plot(
        _col(element.data, "x"), _col(element.data, "y"),
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
        lw=element.line_width, ls=_LINE_STYLE[element.line_style], alpha=element.alpha,
    )
    return line


def render_bars(element: Bars, ctx):
    if element.group is not None:
        return _render_group_bars(element, ctx)
    height = _col(element.data, "y")
    try:
        x = _col(element.data, "x")
    except (ValueError, TypeError):
        x = np.arange(len(height), dtype="float64")
    return ctx.parent_axes.bar(
        x, height, color=_color(element.color, ctx.theme, ctx.series_index).mpl())


def _render_group_bars(element: Bars, ctx):
    """One bar series per group ([D68]) — offset (grouped) or bottom-stacked;
    palette per group in category order + a categorical group legend."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import Legend, category_swatches  # noqa: PLC0415

    d = element.data
    xs, gs, mat = group_bars(np.asarray(d.series("x")), _col(d, "y"),
                             np.asarray(d.series("group")))
    numeric = np.issubdtype(xs.dtype, np.number)
    pos = xs.astype("float64") if numeric else np.arange(len(xs), dtype="float64")
    ax = ctx.parent_axes
    if not numeric:
        ax.set_xticks(pos, [str(c) for c in xs])
    swatches = category_swatches(gs, ctx.theme.palette)
    artists = []
    if element.mode == "grouped":
        total_w = 0.8
        w = total_w / len(gs)
        for gi in range(len(gs)):
            artists.append(ax.bar(pos - total_w / 2 + w / 2 + gi * w, mat[gi],
                                  width=w * 0.95, color=swatches[gi].mpl()))
    else:  # stacked
        bases = np.zeros(len(xs))
        for gi in range(len(gs)):
            artists.append(ax.bar(pos, mat[gi], width=0.6, bottom=bases,
                                  color=swatches[gi].mpl()))
            bases = bases + mat[gi]
    if ctx.show_legend:
        legend = Legend(kind="categorical", title=element.group,
                        entries=tuple((str(g), swatches[i]) for i, g in enumerate(gs)))
        _add_legend(ax, legend, ctx.theme, ctx.legend_position)
    return artists


def render_histogram(element: Histogram, ctx):
    vals = _col(element.data, "column")
    bins = element.bins if isinstance(element.bins, int) else "auto"
    _n, _bins, patches = ctx.parent_axes.hist(
        vals, bins=bins, density=element.density,
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(),
    )
    return patches


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
    values = np.asarray(element.data.grid().values)
    if values.ndim == 3:  # RGBA raster (e.g. a user-built image)
        artist = ctx.parent_axes.imshow(
            values, extent=(x0, x1, y0, y1), origin="lower", aspect="auto",
            interpolation=element.interpolation,
        )
        _wire_dynamic_raster(element, artist, ctx)
        return artist
    return ctx.parent_axes.imshow(
        np.asarray(values, dtype="float64"),
        extent=(x0, x1, y0, y1), origin="lower", aspect="auto", cmap=element.colormap,
        interpolation=element.interpolation,
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
    if not hasattr(ax, "_qtviz_rasters"):
        ax._qtviz_rasters = []
    ax._qtviz_rasters.append(controller)
    ax._qtviz_rasters.append(wire_raster_hover(ax, element.id, ctx.event_bus, holder))


def render_heatmap(element: Heatmap, ctx):
    from ...core._stats import grid_reduce  # noqa: PLC0415

    d = element.data
    _xs, _ys, grid = grid_reduce(d.series("x"), d.series("y"), _col(d, "z"),
                                 element.aggregator)  # real reduction ([D69])
    return ctx.parent_axes.imshow(grid, origin="lower", aspect="auto", cmap=element.colormap)


def render_errorbars(element: ErrorBars, ctx):
    d = element.data
    lo, hi = _col(d, "err_lo"), _col(d, "err_hi")
    err = np.vstack([lo, hi])  # [below, above]
    kwargs = {"yerr": err} if element.direction in ("y", "both") else {"xerr": err}
    return ctx.parent_axes.errorbar(
        _col(d, "x"), _col(d, "y"), fmt="o",
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(), **kwargs,
    )


def render_spread(element: Spread, ctx):
    d = element.data
    return ctx.parent_axes.fill_between(
        _col(d, "x"), _col(d, "y_lo"), _col(d, "y_hi"),
        color=_color(element.color, ctx.theme, ctx.series_index).mpl(), alpha=element.alpha,
    )


def _ref_color(spec, theme) -> Color:
    """Annotation default: the theme foreground — chrome, not a palette series."""
    return Color(spec) if spec is not None else theme.foreground


def render_hline(element: HLine, ctx):
    return ctx.parent_axes.axhline(
        element.y, color=_ref_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_LINE_STYLE[element.line_style], alpha=element.alpha,
    )


def render_vline(element: VLine, ctx):
    return ctx.parent_axes.axvline(
        element.x, color=_ref_color(element.color, ctx.theme).mpl(),
        lw=element.line_width, ls=_LINE_STYLE[element.line_style], alpha=element.alpha,
    )


def render_span(element: Span, ctx):
    fn = ctx.parent_axes.axhspan if element.orient == "h" else ctx.parent_axes.axvspan
    return fn(element.lo, element.hi,
              color=_ref_color(element.color, ctx.theme).mpl(), alpha=element.alpha)


def render_text(element: Text, ctx):
    kwargs = {"color": _ref_color(element.color, ctx.theme).mpl(), "ha": element.anchor}
    if element.size is not None:
        kwargs["fontsize"] = element.size
    return ctx.parent_axes.text(element.x, element.y, element.text, **kwargs)



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
}

# Recommended options each renderer above actually consumes (spec §3.4 / [D51]).
# Anything in an element's RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
# Keep in sync with the renderers — the conformance test guards this.


HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker", "label"}),
    Curve: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Bars: frozenset({"color", "group", "label"}),                # not orient
    Histogram: frozenset({"bins", "density", "color", "label"}),
    Image: frozenset({"colormap", "interpolation"}),
    Heatmap: frozenset({"colormap", "aggregator"}),
    ErrorBars: frozenset({"direction", "color", "label"}),
    Spread: frozenset({"color", "alpha", "label"}),
    HLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    VLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Span: frozenset({"color", "alpha", "label"}),
    Text: frozenset({"color", "size", "anchor"}),
}
