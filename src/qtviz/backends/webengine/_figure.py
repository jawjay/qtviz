"""Element → Plotly figure (the webengine Element-renderer path, D24).

Pure data: no Qt, no WebEngine. Mirrors the pyqtgraph/matplotlib renderers —
by the time these run, `resolve_node` (D14) has replaced each Element's data
with a role-keyed eager ref, so we read channels by role (`"x"`, `"y"`, …).

Output is a plain ``{"data": [...traces], "layout": {...}}`` dict — a Plotly
figure spec that ``PlotlyBackend`` hosts in a ``WebBridgeView``. Building dicts
(not ``plotly.graph_objects``) keeps this layer importable and testable without
plotly installed; the host validates when it renders.
"""

from __future__ import annotations

import numpy as np

from ...core.compose import Overlay
from ...data import resolve_node
from ...elements import Scatter
from ...errors import RendererMissingError

_SIZE_LO, _SIZE_HI = 5.0, 18.0


def _css(color) -> str:
    r, g, b = (int(round(c * 255)) for c in color.rgba[:3])
    return f"rgb({r},{g},{b})"


def _scaled_sizes(values) -> list[float]:
    a = np.asarray(values, dtype="float64")
    vmin, vmax = float(np.nanmin(a)), float(np.nanmax(a))
    span = (vmax - vmin) or 1.0
    return (_SIZE_LO + (a - vmin) / span * (_SIZE_HI - _SIZE_LO)).tolist()


def _element_color(element, theme, idx: int):
    from ...core.color import Color  # noqa: PLC0415

    if element.color is None:
        return theme.palette[idx % len(theme.palette)]
    return Color(element.color)


def _scatter_trace(element: Scatter, theme, idx: int) -> dict:
    d = element.data
    marker: dict = {}
    marker["size"] = (
        _scaled_sizes(d.series("size")) if element.size_by is not None else (element.size or 6)
    )
    if element.color_by is not None:
        from ...core.encoding import map_colors  # noqa: PLC0415
        from ...core.palette import palettes  # noqa: PLC0415

        rgba, _legend = map_colors(
            np.asarray(d.series("color")),
            palette=theme.palette,
            continuous_palette=palettes.get("viridis"),
            title=element.color_by,
        )
        marker["color"] = [
            f"rgb({int(round(r * 255))},{int(round(g * 255))},{int(round(b * 255))})"
            for r, g, b, _a in rgba
        ]
    else:
        marker["color"] = _css(_element_color(element, theme, idx))
    marker["opacity"] = element.alpha
    return {
        "type": "scattergl",
        "mode": "markers",
        "x": np.asarray(d.series("x"), dtype="float64").tolist(),
        "y": np.asarray(d.series("y"), dtype="float64").tolist(),
        "marker": marker,
        "name": element.color_by or element.id,
    }


_TRACE_BUILDERS = {
    Scatter: _scatter_trace,
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
    needs to route pick/select back to the originating Element.
    """
    node = resolve_node(node)
    traces: list[dict] = []
    source_ids: list[str] = []
    for idx, element in enumerate(_elements(node)):
        builder = _TRACE_BUILDERS.get(type(element))
        if builder is None:
            raise RendererMissingError(
                f"webengine has no Plotly renderer for {type(element).__name__}"
            )
        traces.append(builder(element, theme, idx))
        source_ids.append(element.id)
    return {"data": traces, "layout": plotly_layout(theme)}, source_ids


def build_figure(node, theme) -> dict:
    """Resolve `node` and build a Plotly figure spec (one trace per Element)."""
    return build(node, theme)[0]


def plotly_layout(theme) -> dict:
    """A Plotly layout carrying the qtviz Theme (axes/bg/font/palette)."""
    fg = _css(theme.foreground)
    bg = _css(theme.background)
    grid = _css(theme.grid)
    axis = {
        "gridcolor": grid,
        "linecolor": fg,
        "zerolinecolor": grid,
        "tickfont": {"color": fg},
        "title": {"font": {"color": fg}},
    }
    return {
        "paper_bgcolor": bg,
        "plot_bgcolor": bg,
        "font": {"color": fg, "family": theme.font_family, "size": theme.font_size},
        "colorway": [_css(c) for c in theme.palette],
        "xaxis": dict(axis),
        "yaxis": dict(axis),
        "margin": {"l": 50, "r": 20, "t": 30, "b": 40},
        "showlegend": False,
    }
