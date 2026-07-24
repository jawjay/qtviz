"""Element → Plotly figure (the webengine Element-renderer path, D24).

Pure data: no Qt, no WebEngine. Mirrors the pyqtgraph/matplotlib renderers —
by the time these run, `resolve_node` (D14) has replaced each Element's data
with a role-keyed eager ref, so we read channels by role (`"x"`, `"y"`, …).

Output is a plain ``{"data": [...traces], "layout": {...}}`` dict — a Plotly
figure spec that ``PlotlyBackend`` hosts in a ``WebBridgeView``. Building dicts
(not ``plotly.graph_objects``) keeps this layer importable and testable without
plotly installed; the host validates when it renders.

Each builder returns a **list** of traces so a multi-trace element (Spread's
band = two traces) keeps the trace_index → source-id table 1:1.
"""

from __future__ import annotations

import numpy as np

from ...core._degrade import check_recommended
from ...core._scales import log_lim, logify
from ...core.compose import Overlay, effective_scales, surface_of
from ...data import resolve_node
from ...elements import (
    Bars,
    BoxPlot,
    Curve,
    ErrorBars,
    Heatmap,
    Histogram,
    HLine,
    Image,
    RawFigure,
    Scatter,
    Span,
    Spread,
    Text,
    Violin,
    VLine,
)
from ...errors import IncompatibleOverlayError, RendererMissingError

_SIZE_LO, _SIZE_HI = 5.0, 18.0
_DASH = {"solid": "solid", "dashed": "dash", "dotted": "dot", "dashdot": "dashdot"}
# qtviz marker vocabulary → Plotly marker symbols ([D51]).
_SYMBOL = {"circle": "circle", "square": "square", "triangle": "triangle-up",
           "diamond": "diamond", "cross": "x"}


def _css(color) -> str:
    r, g, b = (int(round(c * 255)) for c in color.rgba[:3])
    return f"rgb({r},{g},{b})"


def _rgba_css(color, alpha: float) -> str:
    r, g, b = (int(round(c * 255)) for c in color.rgba[:3])
    return f"rgba({r},{g},{b},{alpha})"


def _element_color(element, theme, idx: int):
    from ...core.color import Color  # noqa: PLC0415

    if getattr(element, "color", None) is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(element.color)


def _floats(series) -> np.ndarray:
    # numpy (not .tolist()) so the figure → go.Figure → Plotly's base64
    # typed-array encoder engages (W5.1a; the encoder is numpy-only).
    return np.asarray(series, dtype="float64")


def _scaled_sizes(values) -> np.ndarray:
    a = np.asarray(values, dtype="float64")
    vmin, vmax = float(np.nanmin(a)), float(np.nanmax(a))
    span = (vmax - vmin) or 1.0
    return _SIZE_LO + (a - vmin) / span * (_SIZE_HI - _SIZE_LO)


def _color_by_list(element, d, theme) -> list[str]:
    from ...core.encoding import map_colors  # noqa: PLC0415
    from ...core.palette import palettes  # noqa: PLC0415

    rgba, _legend = map_colors(
        np.asarray(d.series("color")),
        palette=theme.palette,
        continuous_palette=palettes.get("viridis"),
        title=element.color_by,
    )
    return [
        f"rgb({int(round(r * 255))},{int(round(g * 255))},{int(round(b * 255))})"
        for r, g, b, _a in rgba
    ]


def _continuous_marker_color(element, values, marker: dict) -> None:
    """Continuous `color_by` the Plotly-native way: numeric values + the shared
    viridis ramp as a colorscale + a real `colorbar` — the previously-discarded
    `Legend` finally drawn on webengine ([D55] parity). Truthful linear bounds
    (`cmin`/`cmax` = data range), matching the native colorbars ([D48])."""
    from ...core.palette import palettes  # noqa: PLC0415

    ramp = palettes.get("viridis")
    a = np.asarray(values, dtype="float64")
    marker["color"] = a
    marker["colorscale"] = [[t, _css(ramp.at(t))] for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    marker["cmin"] = float(np.nanmin(a))
    marker["cmax"] = float(np.nanmax(a))
    marker["colorbar"] = {"title": {"text": element.color_by}}


# ── per-element trace builders (each returns a list of Plotly traces) ─────────
def _scatter_trace(element: Scatter, theme, idx: int) -> list[dict]:
    d = element.data
    marker: dict = {
        "size": (
            _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6)
        ),
        "opacity": element.alpha,
        "symbol": _SYMBOL[element.marker],
    }
    if element.color_by is not None:
        from ...core.encoding import is_categorical  # noqa: PLC0415

        values = np.asarray(d.series("color"))
        if is_categorical(values):
            marker["color"] = _color_by_list(element, d, theme)  # per-category key: later
        else:
            _continuous_marker_color(element, values, marker)
    else:
        marker["color"] = _css(_element_color(element, theme, idx))
    return [{
        "type": "scattergl", "mode": "markers",
        "x": _floats(d.series("x")), "y": _floats(d.series("y")),
        "marker": marker, "name": element.label or element.color_by or element.id,
        "showlegend": element.label is not None,
    }]


def _curve_trace(element: Curve, theme, idx: int) -> list[dict]:
    d = element.data
    line = {"color": _css(_element_color(element, theme, idx)), "width": element.line_width,
            "dash": _DASH.get(element.line_style, "solid")}
    return [{
        "type": "scattergl", "mode": "lines",
        "x": _floats(d.series("x")), "y": _floats(d.series("y")),
        "line": line, "opacity": element.alpha, "name": element.label or element.id,
        "showlegend": element.label is not None,
    }]


def _bars_trace(element: Bars, theme, idx: int) -> list[dict]:
    d = element.data
    if element.group is not None:
        return _group_bars_traces(element, theme)
    x = list(np.asarray(d.series("x")))            # keep categorical labels as-is
    trace = {"type": "bar", "marker": {"color": _css(_element_color(element, theme, idx))},
             "name": element.label or element.id, "showlegend": element.label is not None}
    if element.orient == "h":
        trace["y"], trace["x"], trace["orientation"] = x, _floats(d.series("y")), "h"
    else:
        trace["x"], trace["y"] = x, _floats(d.series("y"))
    return [trace]


def _group_bars_traces(element: Bars, theme) -> list[dict]:
    """One bar trace per group ([D68]); the stacking/offset itself is Plotly's
    `layout.barmode`, set by `build`. Palette per group in category order —
    same swatch rule as the native backends."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import category_swatches  # noqa: PLC0415

    d = element.data
    xs, gs, mat = group_bars(np.asarray(d.series("x")),
                             np.asarray(d.series("y"), dtype="float64"),
                             np.asarray(d.series("group")))
    numeric = np.issubdtype(xs.dtype, np.number)
    x = _floats(xs) if numeric else [str(c) for c in xs]
    swatches = category_swatches(gs, theme.palette)
    return [{
        "type": "bar", "x": x, "y": mat[gi],
        "marker": {"color": _css(swatches[gi])},
        "name": str(g), "showlegend": True,
    } for gi, g in enumerate(gs)]


def _histogram_trace(element: Histogram, theme, idx: int) -> list[dict]:
    trace = {
        "type": "histogram", "x": _floats(element.data.series("column")),
        "marker": {"color": _css(_element_color(element, theme, idx))},
        "name": element.label or element.id, "showlegend": element.label is not None,
    }
    if isinstance(element.bins, int):
        trace["nbinsx"] = element.bins
    if element.density:
        trace["histnorm"] = "probability density"
    return [trace]


def _image_trace(element: Image, theme, idx: int) -> list[dict]:
    agg = getattr(element, "_raster_agg", None)
    if agg is not None:  # datashaded raster: shade with the View's Theme (C5, matches native)
        from ...core.palette import palettes  # noqa: PLC0415
        from ...ext.datashader import shade_aggregate  # noqa: PLC0415

        rgba = shade_aggregate(agg, palette=theme.palette,
                               continuous_palette=palettes.get("viridis")).rgba
        return [{"type": "image", "z": rgba, "name": element.id}]
    values = np.asarray(element.data.grid().values)
    x0, y0, x1, y1 = element.bounds
    if values.ndim == 2:
        nrows, ncols = values.shape
        return [{
            "type": "heatmap", "z": values,
            "x": np.linspace(x0, x1, ncols),
            "y": np.linspace(y0, y1, nrows),
            "colorscale": "Viridis", "name": element.id,
        }]
    return [{"type": "image", "z": values, "name": element.id}]  # RGBA raster (user-built)


def _heatmap_trace(element: Heatmap, theme, idx: int) -> list[dict]:
    from ...core._stats import grid_reduce  # noqa: PLC0415

    d = element.data
    xs, ys, grid = grid_reduce(d.series("x"), d.series("y"),
                               np.asarray(d.series("z"), dtype="float64"),
                               element.aggregator)  # real reduction ([D69])
    return [{
        "type": "heatmap", "x": xs, "y": ys, "z": grid,
        "colorscale": "Viridis", "name": element.id,
    }]


def _errorbars_trace(element: ErrorBars, theme, idx: int) -> list[dict]:
    d = element.data
    color = _css(_element_color(element, theme, idx))
    err = {"type": "data", "array": _floats(d.series("err_hi")),
           "arrayminus": _floats(d.series("err_lo")), "symmetric": False, "color": color}
    trace = {
        "type": "scattergl", "mode": "markers",
        "x": _floats(d.series("x")), "y": _floats(d.series("y")),
        "marker": {"color": color}, "name": element.label or element.id,
        "showlegend": element.label is not None,
    }
    trace["error_y" if element.direction in ("y", "both") else "error_x"] = err
    return [trace]


def _spread_trace(element: Spread, theme, idx: int) -> list[dict]:
    d = element.data
    x = _floats(d.series("x"))
    color = _element_color(element, theme, idx)
    line_css = _css(color)
    # lower edge first (no fill), then upper edge filling down to it.
    lo = {"type": "scatter", "mode": "lines", "x": x, "y": _floats(d.series("y_lo")),
          "line": {"width": 0, "color": line_css}, "showlegend": False, "hoverinfo": "skip",
          "name": element.label or element.id}
    hi = {"type": "scatter", "mode": "lines", "x": x, "y": _floats(d.series("y_hi")),
          "line": {"width": 0, "color": line_css}, "fill": "tonexty",
          "fillcolor": _rgba_css(color, element.alpha), "name": element.label or element.id,
          "showlegend": element.label is not None}
    return [lo, hi]



def _dist_groups(element, theme, idx: int):
    """Shared BoxPlot/Violin prep: per-category groups + names + swatches."""
    from ...core._stats import split_by  # noqa: PLC0415
    from ...core.encoding import category_swatches  # noqa: PLC0415

    d = element.data
    cats, groups = split_by(d.series("column"),
                            d.series("by") if element.by is not None else None)
    if cats is not None:
        names = [str(c) for c in cats]
        swatches = category_swatches(cats, theme.palette)
        show = True
    else:
        names = [element.label or element.id] * len(groups)
        swatches = [_element_color(element, theme, idx)] * len(groups)
        show = element.label is not None
    return groups, names, swatches, show


def _boxplot_trace(element: BoxPlot, theme, idx: int) -> list[dict]:
    """Precomputed Plotly box traces from the shared `box_stats` ([D67]) — no
    raw values, so Plotly cannot substitute its own statistics. Outliers ride
    as a separate marker trace (precomputed boxes draw no fliers)."""
    from ...core._stats import box_stats  # noqa: PLC0415

    groups, names, swatches, show = _dist_groups(element, theme, idx)
    traces: list[dict] = []
    for i, g in enumerate(groups):
        s = box_stats(g)
        traces.append({
            "type": "box", "x": [names[i]],
            "q1": [s.q1], "median": [s.median], "q3": [s.q3],
            "lowerfence": [s.lo_whisker], "upperfence": [s.hi_whisker],
            "marker": {"color": _css(swatches[i])}, "opacity": element.alpha,
            "name": names[i], "showlegend": show,
        })
        if len(s.outliers):
            traces.append({
                "type": "scattergl", "mode": "markers",
                "x": [names[i]] * len(s.outliers), "y": _floats(s.outliers),
                "marker": {"color": _css(theme.foreground), "size": 4},
                "name": names[i], "showlegend": False, "hoverinfo": "skip",
            })
    return traces


def _violin_trace(element: Violin, theme, idx: int) -> list[dict]:
    """Filled polygons from the shared `kde` ([D67]) — deliberately NOT Plotly's
    violin trace, whose own KDE would diverge from the native backends."""
    from ...core._stats import kde  # noqa: PLC0415

    groups, names, swatches, show = _dist_groups(element, theme, idx)
    traces: list[dict] = []
    for i, g in enumerate(groups):
        grid, dens = kde(g)
        half = dens / (dens.max() or 1.0) * 0.4
        xs = np.concatenate([i + half, (i - half)[::-1]])
        ys = np.concatenate([grid, grid[::-1]])
        traces.append({
            "type": "scatter", "mode": "lines", "x": xs, "y": ys,
            "fill": "toself", "fillcolor": _rgba_css(swatches[i], element.alpha),
            "line": {"width": 1, "color": _css(swatches[i])},
            "name": names[i], "showlegend": show, "hoverinfo": "skip",
        })
    return traces


_TRACE_BUILDERS = {
    Scatter: _scatter_trace,
    Curve: _curve_trace,
    Bars: _bars_trace,
    Histogram: _histogram_trace,
    Image: _image_trace,
    Heatmap: _heatmap_trace,
    ErrorBars: _errorbars_trace,
    Spread: _spread_trace,
    BoxPlot: _boxplot_trace,
    Violin: _violin_trace,
}

# Recommended options each trace builder above actually consumes (spec §3.4 /
# [D51]). Anything in RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker", "label"}),
    Curve: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Bars: frozenset({"color", "orient", "group", "label"}),
    Histogram: frozenset({"bins", "density", "color", "label"}),
    Image: frozenset(),                          # colorscale hardcoded Viridis
    Heatmap: frozenset({"aggregator"}),          # colorscale still hardcoded
    ErrorBars: frozenset({"direction", "color", "label"}),
    Spread: frozenset({"color", "alpha", "label"}),
    HLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    VLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
    Span: frozenset({"color", "alpha", "label"}),
    Text: frozenset({"color", "size", "anchor"}),
    BoxPlot: frozenset({"by", "color", "alpha", "label"}),
    Violin: frozenset({"by", "color", "alpha", "label"}),
}


def supported_types() -> set[type]:
    return set(_TRACE_BUILDERS)


def _elements(node):
    """The Element children to draw as traces. Layout never reaches a backend
    (can_host is False — the LayoutHost composes panes); a bare Element or an
    Overlay does."""
    if isinstance(node, Overlay):
        return list(node.children)
    return [node]


def _ref_css(element, theme) -> str:
    """Annotation default color: theme foreground — chrome, not a palette series."""
    from ...core.color import Color  # noqa: PLC0415

    color = Color(element.color) if getattr(element, "color", None) is not None \
        else theme.foreground
    return _css(color)


def _shape_coord(value: float, scale: str) -> float | None:
    """One annotation coordinate for a Plotly shape: on a log axis Plotly wants
    log10 values; a non-positive coordinate drops (warned by logify), R1-style."""
    if scale != "log":
        return float(value)
    v = logify(np.array([value], dtype="float64"), True)[0]
    return float(v) if np.isfinite(v) else None


def _line_shape(pos: float | None, axis: str, element, css: str) -> dict | None:
    if pos is None:
        return None
    free = "y" if axis == "x" else "x"
    return {
        "type": "line",
        f"{free}ref": "paper", f"{free}0": 0.0, f"{free}1": 1.0,
        f"{axis}ref": axis, f"{axis}0": pos, f"{axis}1": pos,
        "opacity": element.alpha,
        "line": {"color": css, "width": element.line_width,
                 "dash": _DASH.get(element.line_style, "solid")},
    }


def _shape(element, theme, x_scale: str, y_scale: str) -> dict | None:
    """An HLine / VLine / Span as a Plotly layout shape ([D70])."""
    css = _ref_css(element, theme)
    if isinstance(element, HLine):
        return _line_shape(_shape_coord(element.y, y_scale), "y", element, css)
    if isinstance(element, VLine):
        return _line_shape(_shape_coord(element.x, x_scale), "x", element, css)
    axis = "y" if element.orient == "h" else "x"       # Span
    scale = y_scale if axis == "y" else x_scale
    lo, hi = _shape_coord(element.lo, scale), _shape_coord(element.hi, scale)
    if lo is None or hi is None:
        return None
    free = "x" if axis == "y" else "y"
    return {
        "type": "rect",
        f"{free}ref": "paper", f"{free}0": 0.0, f"{free}1": 1.0,
        f"{axis}ref": axis, f"{axis}0": lo, f"{axis}1": hi,
        "fillcolor": css, "opacity": element.alpha, "line": {"width": 0},
    }


def _note(element: Text, theme, x_scale: str, y_scale: str) -> dict | None:
    """A Text element as a Plotly layout annotation."""
    x, y = _shape_coord(element.x, x_scale), _shape_coord(element.y, y_scale)
    if x is None or y is None:
        return None
    font: dict = {"color": _ref_css(element, theme)}
    if element.size is not None:
        font["size"] = element.size
    return {"x": x, "y": y, "text": element.text, "showarrow": False,
            "font": font, "xanchor": element.anchor}


def build(node, theme) -> tuple[dict, list[str]]:
    """Resolve `node` → (Plotly figure spec, per-trace source-id table).

    The source-id list is the D27 trace_index → Element.id map the event layer
    needs to route pick/select back to the originating Element. Multi-trace
    elements repeat their id once per trace. Annotation elements ([D70]) become
    layout shapes/annotations — no trace, no source-id row (they emit no
    events) — and do not consume a palette slot (`series_index_map` rule).
    """
    surf = surface_of(node)  # before resolve — the shared-surface options (title/labels)
    node = resolve_node(node)
    # effective scales need the *resolved* node — a datashaded Scatter is an Image
    # by now, and the raster gate must see it ([D59]).
    x_scale, y_scale = effective_scales(node, surf, _SUPPORTED_SCALES, "webengine")
    traces: list[dict] = []
    source_ids: list[str] = []
    shapes: list[dict] = []
    notes: list[dict] = []
    idx = 0  # data-series palette slot; annotations excluded
    barmode: str | None = None  # set by a grouped/stacked Bars ([D68])
    for element in _elements(node):
        if isinstance(element, RawFigure):
            raise IncompatibleOverlayError(
                "RawFigure is a whole figure and can't be overlaid; render it on its own"
            )
        check_recommended(
            element, backend_name="webengine",
            honored=HONORED.get(type(element), frozenset()),
        )
        if isinstance(element, (HLine, VLine, Span)):
            shape = _shape(element, theme, x_scale, y_scale)
            if shape is not None:
                shapes.append(shape)
            continue
        if isinstance(element, Text):
            note = _note(element, theme, x_scale, y_scale)
            if note is not None:
                notes.append(note)
            continue
        builder = _TRACE_BUILDERS.get(type(element))
        if builder is None:
            raise RendererMissingError(
                f"webengine has no Plotly renderer for {type(element).__name__}"
            )
        el_traces = builder(element, theme, idx)
        idx += 1
        traces.extend(el_traces)
        source_ids.extend([element.id] * len(el_traces))
        if isinstance(element, Bars) and element.group is not None:
            barmode = "stack" if element.mode == "stacked" else "group"
    layout = plotly_layout(theme, surf, x_scale, y_scale)
    if barmode is not None:
        layout["barmode"] = barmode
    if shapes:
        layout["shapes"] = shapes
    if notes:
        layout["annotations"] = notes
    return {"data": traces, "layout": layout}, source_ids


def build_figure(node, theme) -> dict:
    """Resolve `node` and build a Plotly figure spec."""
    return build(node, theme)[0]


# Axis scales the webengine (Plotly) path renders (axis-surface seam, [D59]).
# Keep in sync with WebEngineBackend.capabilities.scales.
_SUPPORTED_SCALES = frozenset({"linear", "log"})


def _axis(grid: str, fg: str, axis: str, spec=None, eff_scale: str = "linear") -> dict:
    """One Plotly axis dict — its own `title` object (never shared between x/y, so a
    label on one axis can't leak onto the other) — carrying the surface's per-axis
    `AxisSpec` (label / scale / declarative range / invert). Under `type="log"`
    Plotly's `range` is **log₁₀**, so a data-space `lim` is transformed here — the
    outgoing half of the webengine R1 (feasibility §10.2)."""
    title = {"font": {"color": fg}}
    if spec is not None and spec.label:
        title["text"] = spec.label
    d = {
        "gridcolor": grid,
        "linecolor": fg,
        "zerolinecolor": grid,
        "tickfont": {"color": fg},
        "title": title,
    }
    if spec is not None:
        is_log = eff_scale == "log"
        if is_log:
            d["type"] = "log"
        lim = spec.lim
        if lim is not None and is_log:
            lim = log_lim(lim, axis=axis, backend="webengine")
        if lim is not None:
            d["range"] = [lim[0], lim[1]]
        if spec.invert:
            d["autorange"] = "reversed"
    return d


def plotly_layout(theme, surf=None, x_scale: str = "linear", y_scale: str = "linear") -> dict:
    """A Plotly layout carrying the qtviz Theme (axes/bg/font/palette) and, when
    given, the shared-surface options (`OverlayOptions` — title, per-axis labels /
    scale / limits / invert, aspect — axis-surface seam). The caller resolves the
    effective scales (`effective_scales`)."""
    fg = _css(theme.foreground)
    bg = _css(theme.background)
    grid = _css(theme.grid)
    layout = {
        "paper_bgcolor": bg,
        "plot_bgcolor": bg,
        "font": {"color": fg, "family": theme.font_family, "size": theme.font_size},
        "colorway": [_css(c) for c in theme.palette],
        "xaxis": _axis(grid, fg, "x", surf.x if surf else None, x_scale),
        "yaxis": _axis(grid, fg, "y", surf.y if surf else None, y_scale),
        "margin": {"l": 50, "r": 20, "t": 30, "b": 40},
        # ([D55] parity) legends follow the surface switch; traces opt in per-label,
        # so an unlabeled figure shows no opaque-id entries even when enabled.
        "showlegend": surf.legend_enabled if surf is not None else False,
    }
    if surf is not None and surf.legend_position == "top":
        layout["legend"] = {"orientation": "h", "x": 0.0, "y": 1.12}
    if surf is not None and surf.title:
        layout["title"] = {"text": surf.title, "font": {"color": fg}}
    if surf is not None and surf.aspect is not None:
        layout["yaxis"]["scaleanchor"] = "x"
        layout["yaxis"]["scaleratio"] = surf.aspect
    return layout
