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

from ...core.compose import Overlay, surface_of
from ...data import resolve_node
from ...elements import (
    Bars,
    Curve,
    ErrorBars,
    Heatmap,
    Histogram,
    Image,
    RawFigure,
    Scatter,
    Spread,
)
from ...errors import IncompatibleOverlayError, RendererMissingError

_SIZE_LO, _SIZE_HI = 5.0, 18.0
_DASH = {"solid": "solid", "dashed": "dash", "dotted": "dot", "dashdot": "dashdot"}


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


# ── per-element trace builders (each returns a list of Plotly traces) ─────────
def _scatter_trace(element: Scatter, theme, idx: int) -> list[dict]:
    d = element.data
    marker: dict = {
        "size": (
            _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6)
        ),
        "opacity": element.alpha,
    }
    if element.color_by is not None:
        marker["color"] = _color_by_list(element, d, theme)
    else:
        marker["color"] = _css(_element_color(element, theme, idx))
    return [{
        "type": "scattergl", "mode": "markers",
        "x": _floats(d.series("x")), "y": _floats(d.series("y")),
        "marker": marker, "name": element.color_by or element.id,
    }]


def _curve_trace(element: Curve, theme, idx: int) -> list[dict]:
    d = element.data
    line = {"color": _css(_element_color(element, theme, idx)), "width": element.line_width,
            "dash": _DASH.get(element.line_style, "solid")}
    return [{
        "type": "scattergl", "mode": "lines",
        "x": _floats(d.series("x")), "y": _floats(d.series("y")),
        "line": line, "opacity": element.alpha, "name": element.id,
    }]


def _bars_trace(element: Bars, theme, idx: int) -> list[dict]:
    d = element.data
    x = list(np.asarray(d.series("x")))            # keep categorical labels as-is
    trace = {"type": "bar", "marker": {"color": _css(_element_color(element, theme, idx))},
             "name": element.id}
    if element.orient == "h":
        trace["y"], trace["x"], trace["orientation"] = x, _floats(d.series("y")), "h"
    else:
        trace["x"], trace["y"] = x, _floats(d.series("y"))
    return [trace]


def _histogram_trace(element: Histogram, theme, idx: int) -> list[dict]:
    trace = {
        "type": "histogram", "x": _floats(element.data.series("column")),
        "marker": {"color": _css(_element_color(element, theme, idx))}, "name": element.id,
    }
    if isinstance(element.bins, int):
        trace["nbinsx"] = element.bins
    if element.density:
        trace["histnorm"] = "probability density"
    return [trace]


def _image_trace(element: Image, theme, idx: int) -> list[dict]:
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
    return [{"type": "image", "z": values, "name": element.id}]  # RGBA raster


def _heatmap_trace(element: Heatmap, theme, idx: int) -> list[dict]:
    d = element.data
    xv, yv = np.asarray(d.series("x")), np.asarray(d.series("y"))
    zv = np.asarray(d.series("z"), dtype="float64")
    xs, x_inv = np.unique(xv, return_inverse=True)
    ys, y_inv = np.unique(yv, return_inverse=True)
    grid = np.full((len(ys), len(xs)), np.nan)
    grid[y_inv, x_inv] = zv                        # last value wins (aggregator TODO §5.5)
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
        "marker": {"color": color}, "name": element.id,
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
          "name": element.id}
    hi = {"type": "scatter", "mode": "lines", "x": x, "y": _floats(d.series("y_hi")),
          "line": {"width": 0, "color": line_css}, "fill": "tonexty",
          "fillcolor": _rgba_css(color, element.alpha), "name": element.id}
    return [lo, hi]


_TRACE_BUILDERS = {
    Scatter: _scatter_trace,
    Curve: _curve_trace,
    Bars: _bars_trace,
    Histogram: _histogram_trace,
    Image: _image_trace,
    Heatmap: _heatmap_trace,
    ErrorBars: _errorbars_trace,
    Spread: _spread_trace,
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


def build(node, theme) -> tuple[dict, list[str]]:
    """Resolve `node` → (Plotly figure spec, per-trace source-id table).

    The source-id list is the D27 trace_index → Element.id map the event layer
    needs to route pick/select back to the originating Element. Multi-trace
    elements repeat their id once per trace.
    """
    surf = surface_of(node)  # before resolve — the shared-surface options (title/labels)
    node = resolve_node(node)
    traces: list[dict] = []
    source_ids: list[str] = []
    for idx, element in enumerate(_elements(node)):
        if isinstance(element, RawFigure):
            raise IncompatibleOverlayError(
                "RawFigure is a whole figure and can't be overlaid; render it on its own"
            )
        builder = _TRACE_BUILDERS.get(type(element))
        if builder is None:
            raise RendererMissingError(
                f"webengine has no Plotly renderer for {type(element).__name__}"
            )
        el_traces = builder(element, theme, idx)
        traces.extend(el_traces)
        source_ids.extend([element.id] * len(el_traces))
    return {"data": traces, "layout": plotly_layout(theme, surf)}, source_ids


def build_figure(node, theme) -> dict:
    """Resolve `node` and build a Plotly figure spec."""
    return build(node, theme)[0]


def _axis(grid: str, fg: str, label: str | None = None) -> dict:
    """One Plotly axis dict — its own `title` object (never shared between x/y,
    so injecting a label on one axis can't leak onto the other)."""
    title = {"font": {"color": fg}}
    if label:
        title["text"] = label
    return {
        "gridcolor": grid,
        "linecolor": fg,
        "zerolinecolor": grid,
        "tickfont": {"color": fg},
        "title": title,
    }


def plotly_layout(theme, surf=None) -> dict:
    """A Plotly layout carrying the qtviz Theme (axes/bg/font/palette) and, when
    given, the shared-surface options (`OverlayOptions` title / axis labels —
    axis-surface seam, Phase A)."""
    fg = _css(theme.foreground)
    bg = _css(theme.background)
    grid = _css(theme.grid)
    layout = {
        "paper_bgcolor": bg,
        "plot_bgcolor": bg,
        "font": {"color": fg, "family": theme.font_family, "size": theme.font_size},
        "colorway": [_css(c) for c in theme.palette],
        "xaxis": _axis(grid, fg, surf.x_label if surf else None),
        "yaxis": _axis(grid, fg, surf.y_label if surf else None),
        "margin": {"l": 50, "r": 20, "t": 30, "b": 40},
        "showlegend": False,
    }
    if surf is not None and surf.title:
        layout["title"] = {"text": surf.title, "font": {"color": fg}}
    return layout
