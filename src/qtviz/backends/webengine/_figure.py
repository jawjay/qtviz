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
# mypy: disable-error-code="attr-defined, index, call-overload, assignment, operator"
# (builds heterogeneous Plotly spec dicts + post-resolve shape access)

from __future__ import annotations

from typing import Any

import numpy as np

from ...core._degrade import FULL_SURFACE, check_recommended, check_surface
from ...core._scales import log_lim, logify
from ...core.compose import Overlay, effective_scales, surface_of
from ...data import resolve_node
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
    RawFigure,
    Rect,
    RefLine,
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


def _dash(style) -> str:
    """Named style or a dash tuple in points ([D99]) → Plotly dash string."""
    if isinstance(style, str):
        return _DASH.get(style, "solid")
    return ",".join(f"{v:g}px" for v in style)


# qtviz marker vocabulary → Plotly marker symbols ([D51]/[D99]; Plotly "cross"
# is the plus shape, "x" the diagonal one).
_SYMBOL = {"circle": "circle", "square": "square", "triangle": "triangle-up",
           "triangle_down": "triangle-down", "diamond": "diamond", "cross": "x",
           "plus": "cross", "star": "star", "pentagon": "pentagon",
           "hexagon": "hexagon"}


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
    from ...core._time import as_float_seconds  # noqa: PLC0415

    return as_float_seconds(series)  # datetime64 → epoch s ([D94])


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
        norm=getattr(element, "color_norm", "linear"),
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
        if is_categorical(values) or element.color_norm == "log":
            # categorical, or log-normed continuous: pre-mapped css colors — a
            # linear Plotly colorbar would lie about a log mapping ([D48])
            marker["color"] = _color_by_list(element, d, theme)
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


# qtviz step vocabulary → Plotly line shapes ([D84]).
_LINE_SHAPE = {"pre": "vh", "mid": "hvh", "post": "hv"}


def _curve_color_by_traces(element: Curve, theme) -> list[dict] | None:
    """Categorical per-segment coloring ([D100]) — one NaN-gapped trace per
    category from the shared core split; a continuous column warns (no
    per-segment gradient line in Plotly either) and falls through."""
    from ...core._stats import categorical_line_split  # noqa: PLC0415
    from ...core.encoding import category_swatches, is_categorical  # noqa: PLC0415

    d = element.data
    values = np.asarray(d.series("color"))
    if not is_categorical(values):
        import warnings  # noqa: PLC0415

        from ...errors import QtvizWarning  # noqa: PLC0415

        warnings.warn("webengine: continuous Curve color_by (a per-segment "
                      "gradient line) is matplotlib-only; drawing a "
                      "single-color line.", QtvizWarning, stacklevel=2)
        return None
    cats, parts = categorical_line_split(_floats(d.series("x")),
                                         _floats(d.series("y")), values)
    swatches = category_swatches(cats, theme.palette)
    return [{
        "type": "scattergl", "mode": "lines", "x": xs, "y": ys,
        "line": {"color": _css(sw), "width": element.line_width,
                 "dash": _dash(element.line_style)},
        "opacity": element.alpha, "name": str(c), "showlegend": True,
    } for (xs, ys), sw, c in zip(parts, swatches, cats, strict=True)]


def _curve_trace(element: Curve, theme, idx: int) -> list[dict]:
    d = element.data
    if element.color_by is not None:
        traces = _curve_color_by_traces(element, theme)
        if traces is not None:
            return traces
    color = _css(_element_color(element, theme, idx))
    line = {"color": color, "width": element.line_width,
            "dash": _dash(element.line_style)}
    if element.step is not None:
        line["shape"] = _LINE_SHAPE[element.step]
    every = element.marker_every
    marked_inline = element.marker is not None and every == 1
    trace = {
        # scattergl only draws linear/hv line shapes — stepped curves take the
        # SVG trace (step charts are small; huge data goes through datashader)
        "type": "scatter" if element.step is not None else "scattergl",
        "mode": "lines+markers" if marked_inline else "lines",
        "x": _floats(d.series("x")), "y": _floats(d.series("y")),
        "line": line, "opacity": element.alpha, "name": element.label or element.id,
        "showlegend": element.label is not None,
    }
    if marked_inline:
        trace["marker"] = {"symbol": _SYMBOL[element.marker], "color": color, "size": 7}
        return [trace]
    if element.marker is not None:  # marker_every > 1: a thinned points trace ([D99])
        dots = {
            "type": trace["type"], "mode": "markers",
            "x": _floats(d.series("x"))[::every], "y": _floats(d.series("y"))[::every],
            "marker": {"symbol": _SYMBOL[element.marker], "color": color, "size": 7},
            "opacity": element.alpha, "name": element.label or element.id,
            "showlegend": False, "hoverinfo": "skip",
        }
        return [trace, dots]
    return [trace]


def _bars_trace(element: Bars, theme, idx: int) -> list[dict]:
    d = element.data
    if element.group is not None:
        return _group_bars_traces(element, theme)
    x = list(np.asarray(d.series("x")))            # keep categorical labels as-is
    if element.color_by is not None:  # per-bar colors ([D100])
        from ...core.encoding import is_categorical  # noqa: PLC0415

        values = np.asarray(d.series("color"))
        marker: dict = {}
        if is_categorical(values):
            marker["color"] = _color_by_list(element, d, theme)
        else:
            _continuous_marker_color(element, values, marker)
    else:
        marker = {"color": _css(_element_color(element, theme, idx))}
    trace = {"type": "bar", "marker": marker,
             "name": element.label or element.id, "showlegend": element.label is not None}
    if element.orient == "h":
        trace["y"], trace["x"], trace["orientation"] = x, _floats(d.series("y")), "h"
    else:
        trace["x"], trace["y"] = x, _floats(d.series("y"))
    _bar_text(trace, np.asarray(d.series("y"), dtype="float64"), element)
    return [trace]


def _bar_text(trace: dict, values, element) -> None:
    """Value labels on a bar trace ([D98]) — formatted via [D86]."""
    if element.bar_labels is None:
        return
    from ...core._ticks import format_tick  # noqa: PLC0415

    spec = element.bar_labels if element.bar_labels != "auto" else "g"
    trace["text"] = [format_tick(float(v), spec) for v in values]
    trace["textposition"] = "inside" if element.mode == "stacked" else "outside"


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
    cats = _floats(xs) if numeric else [str(c) for c in xs]
    swatches = category_swatches(gs, theme.palette)
    horizontal = element.orient == "h"  # categories on y, lengths on x ([D85])
    traces = [{
        "type": "bar",
        **({"x": mat[gi], "y": cats, "orientation": "h"} if horizontal
           else {"x": cats, "y": mat[gi]}),
        "marker": {"color": _css(swatches[gi])},
        "name": str(g), "showlegend": True,
    } for gi, g in enumerate(gs)]
    for gi, tr in enumerate(traces):
        _bar_text(tr, mat[gi], element)
    return traces


# qtviz colormap names (matplotlib vocabulary) → Plotly named colorscales.
_COLORSCALES = {
    "viridis": "Viridis", "plasma": "Plasma", "inferno": "Inferno",
    "magma": "Magma", "cividis": "Cividis", "greys": "Greys", "hot": "Hot",
    "jet": "Jet", "rainbow": "Rainbow", "rdbu": "RdBu", "picnic": "Picnic",
    "portland": "Portland", "ylgnbu": "YlGnBu", "ylorrd": "YlOrRd",
    "blues": "Blues", "greens": "Greens", "reds": "Reds", "bluered": "Bluered",
}


def _colorscale(name: str) -> str:
    scale = _COLORSCALES.get(name.lower())
    if scale is None:
        import warnings  # noqa: PLC0415

        from ...errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(
            f"webengine: colormap {name!r} has no Plotly colorscale; using 'Viridis'",
            QtvizWarning, stacklevel=2,
        )
        return "Viridis"
    return scale


def _histogram_trace(element: Histogram, theme, idx: int) -> list[dict]:
    from ...core._stats import histogram  # noqa: PLC0415

    counts, edges = histogram(element.data.series("column"), element.bins,
                              density=element.density)  # shared binning ([D93]) —
    # a pre-binned bar trace, not a Plotly histogram: every backend draws the
    # same bars instead of Plotly re-binning client-side.
    return [{
        "type": "bar",
        "x": _floats((edges[:-1] + edges[1:]) / 2.0), "y": _floats(counts),
        "width": _floats(np.diff(edges)),
        "marker": {"color": _css(_element_color(element, theme, idx))},
        "opacity": element.alpha,
        "name": element.label or element.id, "showlegend": element.label is not None,
    }]


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
        trace = {
            "type": "heatmap", "z": values,
            "x": np.linspace(x0, x1, ncols),
            "y": np.linspace(y0, y1, nrows),
            "colorscale": _colorscale(element.colormap),
            "zsmooth": "best" if element.interpolation == "bilinear" else False,
            "name": element.id,
        }
        _apply_norm(trace, element, values)
        return [trace]
    return [{"type": "image", "z": values, "name": element.id}]  # RGBA raster (user-built)


def _heatmap_trace(element: Heatmap, theme, idx: int) -> list[dict]:
    from ...core._stats import grid_reduce  # noqa: PLC0415

    d = element.data
    xs, ys, grid = grid_reduce(d.series("x"), d.series("y"),
                               np.asarray(d.series("z"), dtype="float64"),
                               element.aggregator)  # real reduction ([D69])
    trace = {
        "type": "heatmap", "x": xs, "y": ys, "z": grid,
        "colorscale": _colorscale(element.colormap), "name": element.id,
    }
    _apply_norm(trace, element, grid)
    return [trace]


def _apply_norm(trace: dict, element, values) -> None:
    """[D105] on Plotly: a linear norm keeps raw z with zmin/zmax (the native
    colorbar stays honest); log/power replace z with the core-normalized grid
    and hide the scale — a linear Plotly colorbar over a non-linear mapping
    would lie ([D48]), and webengine raster keys are a standing soft spot."""
    from ...core.encoding import norm_engaged, normalize_values  # noqa: PLC0415

    if not norm_engaged(element):
        return
    if element.norm == "linear":
        normed, lo, hi = normalize_values(values, norm="linear", vmin=element.vmin,
                                          vmax=element.vmax)
        trace["zmin"], trace["zmax"] = lo, hi
        return
    normed, _lo, _hi = normalize_values(values, norm=element.norm, vmin=element.vmin,
                                        vmax=element.vmax, gamma=element.gamma)
    trace["z"] = normed
    trace["zmin"], trace["zmax"] = 0.0, 1.0
    trace["showscale"] = False


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
    if element.direction in ("y", "both"):
        trace["error_y"] = err
    if element.direction in ("x", "both"):
        trace["error_x"] = dict(err)  # not aliased to error_y
    return [trace]


def _spread_trace(element: Spread, theme, idx: int) -> list[dict]:
    d = element.data
    color = _element_color(element, theme, idx)
    line_css = _css(color)
    common = {"type": "scatter", "mode": "lines",
              "line": {"width": 0, "color": line_css},
              "name": element.label or element.id}
    if element.orient == "h":  # ([D99]) band spans x as a function of y
        y = _floats(d.series("y"))
        lo = {**common, "x": _floats(d.series("x_lo")), "y": y,
              "showlegend": False, "hoverinfo": "skip"}
        hi = {**common, "x": _floats(d.series("x_hi")), "y": y, "fill": "tonextx",
              "fillcolor": _rgba_css(color, element.alpha),
              "showlegend": element.label is not None}
        return [lo, hi]
    x = _floats(d.series("x"))
    # lower edge first (no fill), then upper edge filling down to it.
    lo = {**common, "x": x, "y": _floats(d.series("y_lo")),
          "showlegend": False, "hoverinfo": "skip"}
    hi = {**common, "x": x, "y": _floats(d.series("y_hi")), "fill": "tonexty",
          "fillcolor": _rgba_css(color, element.alpha),
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


def _area_traces(element: Area, theme, idx: int) -> list[dict]:
    """Filled series ([D84b]): tozeroy fill, or per-group bands (Plotly's
    stackgroup does the stacking — same sums as the native cumulative bases)."""
    from ...core._stats import group_bars  # noqa: PLC0415
    from ...core.encoding import category_swatches  # noqa: PLC0415

    d = element.data
    if element.group is None:
        color = _element_color(element, theme, idx)
        return [{
            "type": "scatter", "mode": "lines",
            "x": _floats(d.series("x")), "y": _floats(d.series("y")),
            "line": {"color": _css(color), "width": 1.5}, "fill": "tozeroy",
            "fillcolor": _rgba_css(color, element.alpha),
            "name": element.label or element.id,
            "showlegend": element.label is not None,
        }]
    xs, gs, mat = group_bars(np.asarray(d.series("x")),
                             np.asarray(d.series("y"), dtype="float64"),
                             np.asarray(d.series("group")))
    numeric = np.issubdtype(xs.dtype, np.number)
    x = _floats(xs) if numeric else [str(c) for c in xs]
    swatches = category_swatches(gs, theme.palette)
    traces = []
    for gi, g in enumerate(gs):
        tr = {
            "type": "scatter", "mode": "lines", "x": x, "y": _floats(mat[gi]),
            "line": {"color": _css(swatches[gi]), "width": 1.5},
            "fillcolor": _rgba_css(swatches[gi], element.alpha),
            "name": str(g), "showlegend": True,
        }
        if element.mode == "stacked":
            tr["stackgroup"] = "qtviz"  # Plotly stacks + fills to the band below
        else:
            tr["fill"] = "tozeroy"
        traces.append(tr)
    return traces


def _ecdf_trace(element: Ecdf, theme, idx: int) -> list[dict]:
    from ...core._stats import ecdf  # noqa: PLC0415

    xs, fr = ecdf(element.data.series("column"))
    return [{
        "type": "scatter", "mode": "lines", "x": _floats(xs), "y": _floats(fr),
        "line": {"color": _css(_element_color(element, theme, idx)),
                 "width": element.line_width, "shape": "hv"},  # post-step
        "opacity": element.alpha, "name": element.label or element.id,
        "showlegend": element.label is not None,
    }]


def _pie_trace(element: Pie, theme, idx: int) -> list[dict]:
    d = element.data
    vals = _floats(d.series("values"))
    trace = {
        "type": "pie", "values": vals, "hole": element.hole,
        "opacity": element.alpha,
        "marker": {"colors": [_css(theme.palette[i % len(theme.palette)])
                              for i in range(len(vals))]},
        "name": element.id, "showlegend": element.labels is not None,
        "sort": False,  # keep row order so slice colors match the native pie
    }
    if element.labels is not None:
        trace["labels"] = [str(v) for v in np.asarray(d.series("labels"))]
    return [trace]


def _mesh_trace(element: Mesh, theme, idx: int) -> list[dict]:
    """Non-uniform grid ([D106]): a Plotly heatmap whose x/y carry one more
    entry than z — Plotly reads them as block boundaries (the edges)."""
    values = element.check_shape(element.data.grid().values)
    trace = {
        "type": "heatmap", "z": values,
        "x": np.asarray(element.x_edges, dtype="float64"),
        "y": np.asarray(element.y_edges, dtype="float64"),
        "colorscale": _colorscale(element.colormap), "name": element.id,
    }
    _apply_norm(trace, element, values)
    return [trace]


def _contour_trace(element: Contour, theme, idx: int) -> list[dict]:
    """Iso-lines / filled bands ([D89]). Plotly takes uniform start/end/size
    levels — exactly what the shared core levels are for an int `levels`; a
    non-uniform explicit sequence approximates and warns."""
    from ...core._stats import contour_levels  # noqa: PLC0415

    values = np.asarray(element.data.grid().values, dtype="float64")
    lv = contour_levels(values, element.levels)
    step = float(lv[1] - lv[0]) if len(lv) > 1 else 1.0
    if len(lv) > 2 and not np.allclose(np.diff(lv), step):
        import warnings  # noqa: PLC0415

        from ...errors import QtvizWarning  # noqa: PLC0415

        warnings.warn("webengine: Plotly contours are uniformly spaced; the "
                      "non-uniform `levels` sequence was approximated.",
                      QtvizWarning, stacklevel=2)
    x0, y0, x1, y1 = element.bounds
    ny, nx = values.shape
    return [{
        "type": "contour", "z": values,
        "x": np.linspace(x0, x1, nx), "y": np.linspace(y0, y1, ny),
        "colorscale": _colorscale(element.colormap),
        "contours": {"coloring": "fill" if element.filled else "lines",
                     "start": float(lv[0]), "end": float(lv[-1]), "size": step},
        "line": {"width": element.line_width},
        "showscale": element.filled,  # colorbar for filled, like matplotlib
        "name": element.label or element.id, "showlegend": False,
    }]


_TRACE_BUILDERS: dict[type, Any] = {
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
    Area: _area_traces,
    Ecdf: _ecdf_trace,
    Pie: _pie_trace,
    Contour: _contour_trace,
    Mesh: _mesh_trace,
}

# Recommended options each trace builder above actually consumes (spec §3.4 /
# [D51]). Anything in RECOMMENDED_OPTIONS but NOT here warns-and-degrades.
HONORED: dict[type, frozenset[str]] = {
    Scatter: frozenset({"color", "color_by", "size", "size_by", "alpha", "marker",
                        "color_norm", "label", "axis"}),
    Curve: frozenset({"color", "color_by", "line_width", "line_style", "marker",
                      "marker_every", "step", "alpha", "label", "axis"}),
    Bars: frozenset({"color", "color_by", "orient", "group", "mode",
                     "bar_labels", "label"}),
    Histogram: frozenset({"bins", "density", "color", "alpha", "label"}),
    Image: frozenset({"colormap", "interpolation", "norm", "vmin", "vmax", "gamma"}),
    Heatmap: frozenset({"colormap", "aggregator", "norm", "vmin", "vmax", "gamma"}),
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
    RefLine: frozenset({"color", "line_width", "line_style", "alpha", "label"}),
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
    """One annotation coordinate for a Plotly shape: a log axis wants log10
    values, a date axis wants epoch **ms** ([D94]); a non-positive coordinate
    under log drops (warned by logify), R1-style."""
    if scale == "time":
        return float(value) * 1000.0
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
                 "dash": _dash(element.line_style)},
    }


def _refline_shape(element, theme, traces, x_scale: str, y_scale: str) -> dict | None:
    """`y = slope·x + intercept` as a long segment spanning 3× the data range
    ([D99]) — Plotly shapes can't be infinite-with-slope, so wide zoom-out can
    run off its end (documented caveat). No log-scale form (warn + drop)."""
    if x_scale in ("log", "symlog") or y_scale in ("log", "symlog"):
        import warnings  # noqa: PLC0415

        from ...errors import QtvizWarning  # noqa: PLC0415

        warnings.warn("webengine: RefLine is a straight data-space line and has "
                      "no log-scale form; it was dropped.", QtvizWarning, stacklevel=2)
        return None
    lo, hi = 0.0, 1.0
    xs = [np.asarray(tr["x"], dtype="float64")
          for tr in traces
          if isinstance(tr.get("x"), np.ndarray) and np.asarray(tr["x"]).dtype.kind == "f"]
    if xs:
        finite = np.concatenate([x[np.isfinite(x)] for x in xs])
        if len(finite):
            lo, hi = float(finite.min()), float(finite.max())
    span = (hi - lo) or 1.0
    x0, x1 = lo - span, hi + span
    if x_scale == "time":  # trace arrays are already epoch ms ([D94])
        x0, x1 = x0 / 1000.0, x1 / 1000.0  # back to data seconds for the maths
    y0 = element.slope * x0 + element.intercept
    y1 = element.slope * x1 + element.intercept
    return {
        "type": "line", "xref": "x", "yref": "y",
        "x0": _shape_coord(x0, x_scale), "x1": _shape_coord(x1, x_scale),
        "y0": _shape_coord(y0, y_scale), "y1": _shape_coord(y1, y_scale),
        "opacity": element.alpha,
        "line": {"color": _ref_css(element, theme), "width": element.line_width,
                 "dash": _dash(element.line_style)},
    }


def _outline_shape(points, element, css: str, x_scale: str, y_scale: str) -> dict | None:
    """A closed data-space outline ([D97]) as a Plotly `path` shape."""
    from ...core._geometry import svg_path  # noqa: PLC0415

    xs = [_shape_coord(float(x), x_scale) for x, _y in points]
    ys = [_shape_coord(float(y), y_scale) for _x, y in points]
    if any(v is None for v in xs) or any(v is None for v in ys):
        return None
    shape = {"type": "path", "path": svg_path(list(zip(xs, ys, strict=True))),
             "xref": "x", "yref": "y", "opacity": element.alpha,
             "line": {"color": css, "width": element.line_width}}
    if element.fill:
        shape["fillcolor"] = css
    return shape


def _shape(element, theme, x_scale: str, y_scale: str) -> dict | None:
    """An HLine / VLine / Span / Rect / Ellipse / Polygon as a Plotly layout
    shape ([D70]/[D97])."""
    css = _ref_css(element, theme)
    if isinstance(element, HLine):
        return _line_shape(_shape_coord(element.y, y_scale), "y", element, css)
    if isinstance(element, VLine):
        return _line_shape(_shape_coord(element.x, x_scale), "x", element, css)
    if isinstance(element, Rect):
        x0, x1 = _shape_coord(element.x0, x_scale), _shape_coord(element.x1, x_scale)
        y0, y1 = _shape_coord(element.y0, y_scale), _shape_coord(element.y1, y_scale)
        if None in (x0, x1, y0, y1):
            return None
        shape = {"type": "rect", "xref": "x", "yref": "y",
                 "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                 "opacity": element.alpha,
                 "line": {"color": css, "width": element.line_width}}
        if element.fill:
            shape["fillcolor"] = css
        return shape
    if isinstance(element, Ellipse):
        from ...core._geometry import ellipse_points  # noqa: PLC0415

        return _outline_shape(
            ellipse_points(element.cx, element.cy, element.rx, element.ry,
                           element.angle), element, css, x_scale, y_scale)
    if isinstance(element, Polygon):
        from ...core._geometry import close_points  # noqa: PLC0415

        return _outline_shape(close_points(element.points), element, css,
                              x_scale, y_scale)
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


# Arrow head vocabulary → Plotly arrowside ([D96]).
_ARROWSIDE = {"end": "end", "both": "end+start", "none": "none"}
_YANCHOR = {"center": "middle", "top": "top", "bottom": "bottom"}


def _note(element, theme, x_scale: str, y_scale: str) -> dict | None:
    """A Text or Arrow element as a Plotly layout annotation ([D96])."""
    css = _ref_css(element, theme)
    if isinstance(element, Arrow):
        x1, y1 = _shape_coord(element.x1, x_scale), _shape_coord(element.y1, y_scale)
        x0, y0 = _shape_coord(element.x0, x_scale), _shape_coord(element.y0, y_scale)
        if None in (x0, y0, x1, y1):
            return None
        return {"x": x1, "y": y1, "ax": x0, "ay": y0,
                "axref": "x", "ayref": "y", "text": "", "showarrow": True,
                "arrowhead": 2, "arrowside": _ARROWSIDE[element.head],
                "arrowcolor": css, "arrowwidth": max(element.line_width, 0.3),
                "opacity": element.alpha}
    x, y = _shape_coord(element.x, x_scale), _shape_coord(element.y, y_scale)
    if x is None or y is None:
        return None
    font: dict = {"color": css}
    if element.size is not None:
        font["size"] = element.size
    note = {"x": x, "y": y, "text": element.text.replace("\n", "<br>"),
            "showarrow": False, "font": font, "xanchor": element.anchor,
            "yanchor": _YANCHOR[element.anchor_v],
            "textangle": -element.rotation}  # Plotly rotates clockwise
    if element.frame:
        note["bordercolor"] = css
        note["borderwidth"] = 1
        note["bgcolor"] = _css(theme.background)
        note["borderpad"] = 3
    return note


def build(node, theme) -> tuple[dict, list[str]]:
    """Resolve `node` → (Plotly figure spec, per-trace source-id table).

    The source-id list is the D27 trace_index → Element.id map the event layer
    needs to route pick/select back to the originating Element. Multi-trace
    elements repeat their id once per trace. Annotation elements ([D70]) become
    layout shapes/annotations — no trace, no source-id row (they emit no
    events) — and do not consume a palette slot (`series_index_map` rule).
    """
    surf = surface_of(node)  # before resolve — the shared-surface options (title/labels)
    check_surface(surf, consumer="webengine", honored=FULL_SURFACE)  # ([D109])
    node = resolve_node(node)
    # effective scales need the *resolved* node — a datashaded Scatter is an Image
    # by now, and the raster gate must see it ([D59]).
    x_scale, y_scale = effective_scales(node, surf, _SUPPORTED_SCALES, "webengine")
    traces: list[dict] = []
    source_ids: list[str] = []
    shapes: list[dict] = []
    notes: list[dict] = []
    reflines: list = []  # need the data span — built after the trace loop ([D99])
    idx = 0  # data-series palette slot; annotations excluded
    barmode: str | None = None  # set by a grouped/stacked Bars ([D68])
    y2_active = False  # any child on the twin axis ([D88])
    for element in _elements(node):
        if isinstance(element, RawFigure):
            raise IncompatibleOverlayError(
                "RawFigure is a whole figure and can't be overlaid; render it on its own"
            )
        check_recommended(
            element, backend_name="webengine",
            honored=HONORED.get(type(element), frozenset()),
        )
        if isinstance(element, RefLine):
            reflines.append(element)
            continue
        if isinstance(element, (HLine, VLine, Span, Rect, Ellipse, Polygon)):
            shape = _shape(element, theme, x_scale, y_scale)
            if shape is not None:
                shapes.append(shape)
            continue
        if isinstance(element, (Text, Arrow)):
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
        if getattr(element, "axis", "y") == "y2":  # twin axis ([D88])
            for tr in el_traces:
                tr["yaxis"] = "y2"
            y2_active = True
        traces.extend(el_traces)
        source_ids.extend([element.id] * len(el_traces))
        if isinstance(element, Bars) and element.group is not None:
            barmode = "stack" if element.mode == "stacked" else "group"
    y2 = None
    if y2_active:
        from ...core.compose import resolve_scale  # noqa: PLC0415
        from ...core.options import AxisSpec  # noqa: PLC0415

        y2_spec = surf.y2 if surf.y2 is not None else AxisSpec()
        y2 = (y2_spec, resolve_scale(y2_spec.scale, _SUPPORTED_SCALES,
                                     axis="y2", backend="webengine"))
    for key, scale in (("x", x_scale), ("y", y_scale)):
        if scale != "time":
            continue
        for tr in traces:  # canonical epoch seconds → Plotly date-axis ms ([D94])
            vals = tr.get(key)
            if vals is not None and getattr(vals, "dtype", None) is not None:
                tr[key] = np.asarray(vals, dtype="float64") * 1000.0
    for rl in reflines:
        shape = _refline_shape(rl, theme, traces, x_scale, y_scale)
        if shape is not None:
            shapes.append(shape)
    if not surf.legend_enabled:  # the one legend switch silences colorbars too
        for tr in traces:
            if "showscale" in tr:
                tr["showscale"] = False
    layout = plotly_layout(theme, surf, x_scale, y_scale, y2=y2)
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
_SUPPORTED_SCALES = frozenset({"linear", "log", "time"})  # time: [D94]


def _axis(grid: str, fg: str, axis: str, spec=None, eff_scale: str = "linear") -> dict:
    """One Plotly axis dict — its own `title` object (never shared between x/y, so a
    label on one axis can't leak onto the other) — carrying the surface's per-axis
    `AxisSpec` (label / scale / declarative range / invert). Under `type="log"`
    Plotly's `range` is **log₁₀**, so a data-space `lim` is transformed here — the
    outgoing half of the webengine R1 (feasibility §10.2)."""
    title = {"font": {"color": fg}}
    if spec is not None and spec.label:
        title["text"] = spec.label
    d: dict[str, Any] = {
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
        elif eff_scale == "time":  # data arrives as epoch ms on a date axis ([D94])
            d["type"] = "date"
        lim = spec.lim
        if lim is not None and is_log:
            lim = log_lim(lim, axis=axis, backend="webengine")
        elif lim is not None and eff_scale == "time":
            lim = (lim[0] * 1000.0, lim[1] * 1000.0)  # data-space s → Plotly ms
        if lim is not None:
            d["range"] = [lim[0], lim[1]]
        if spec.invert:
            d["autorange"] = "reversed"
        if spec.tick_format != "auto":  # ([D86]/[D102])
            from ...core._ticks import _STRFTIME, plotly_tick_parts  # noqa: PLC0415

            if _STRFTIME.search(spec.tick_format) and "{" not in spec.tick_format:
                # d3-time-format shares strftime's %-codes on a date axis
                d["tickformat"] = spec.tick_format
            else:
                parts = plotly_tick_parts(spec.tick_format)
                if parts is None:
                    import warnings  # noqa: PLC0415

                    from ...errors import QtvizWarning  # noqa: PLC0415

                    warnings.warn(
                        f"webengine: tick_format {spec.tick_format!r} has no "
                        "d3 translation; using the axis default.",
                        QtvizWarning, stacklevel=2)
                else:
                    prefix, fmt, suffix = parts
                    if prefix:
                        d["tickprefix"] = prefix
                    if fmt:
                        d["tickformat"] = fmt
                    if suffix:
                        d["ticksuffix"] = suffix
        if spec.ticks is not None:  # explicit ticks ([D101]) — data values;
            # a date axis wants ms, log/linear take them raw
            scale_ms = 1000.0 if eff_scale == "time" else 1.0
            d["tickvals"] = [float(v) * scale_ms for v in spec.ticks]
            if spec.tick_labels is not None:
                d["ticktext"] = list(spec.tick_labels)
        if spec.minor:  # ([D103])
            d["minor"] = {"ticks": "outside", "showgrid": False}
        if spec.tick_rotation:
            d["tickangle"] = -spec.tick_rotation  # Plotly rotates clockwise
    return d


def plotly_layout(theme, surf=None, x_scale: str = "linear", y_scale: str = "linear",
                  y2=None) -> dict:
    """A Plotly layout carrying the qtviz Theme (axes/bg/font/palette) and, when
    given, the shared-surface options (`OverlayOptions` — title, per-axis labels /
    scale / limits / invert, aspect — axis-surface seam). The caller resolves the
    effective scales (`effective_scales`); `y2` is `(AxisSpec, effective_scale)`
    for the twin right-hand axis when any trace rides it ([D88])."""
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
    if surf is not None and surf.background is not None:
        from ...core.color import Color  # noqa: PLC0415

        layout["plot_bgcolor"] = _css(Color(surf.background))  # plot area only
    if surf is not None and not surf.grid:  # ([D87])
        layout["xaxis"]["showgrid"] = False
        layout["yaxis"]["showgrid"] = False
    if surf is not None and surf.legend_position == "top":
        layout["legend"] = {"orientation": "h", "x": 0.0, "y": 1.12}
    if surf is not None and surf.title:
        layout["title"] = {"text": surf.title, "font": {"color": fg}}
    if surf is not None and surf.aspect is not None:
        layout["yaxis"]["scaleanchor"] = "x"
        layout["yaxis"]["scaleratio"] = surf.aspect
    if y2 is not None:  # twin axis ([D88])
        y2_spec, y2_scale = y2
        d2 = _axis(grid, fg, "y2", y2_spec, y2_scale)
        d2["overlaying"] = "y"
        d2["side"] = "right"
        d2["showgrid"] = False  # two grids on one surface fight
        layout["yaxis2"] = d2
    return layout
