"""Mark → Plotly-op adapter — the webengine [D122] drawer.

Webengine is not a widget renderer: a mark becomes a **TraceOp** —
`("trace", dict)`, `("shape", dict)`, `("note", dict)`, or `("refline", Rule)`
(deferred: a sloped rule needs the final data span, computed after the trace
loop, [D99]) — and `_figure.build` folds the ops into the figure spec. This
replaces the annotation isinstance ladder: the 9 annotation types arrive here
as 5 mark kinds. Coordinates pass through `_shape_coord` (log10 for log axes,
epoch ms for time, warn-drop for non-positive under log — R1 at the spec
boundary, exactly the pre-IR rules). Plotly rotates clockwise; the [D96] CCW
convention flips sign here, stated once.
"""

from __future__ import annotations

import numpy as np

from ...core.marks import (
    ArrowMark,
    Band,
    Markers,
    PolygonMark,
    Polyline,
    Rule,
    SpanMark,
    TextMark,
)
from ._figure import _SYMBOL, _css, _dash, _rgba_css, _shape_coord

Op = tuple[str, "dict | Rule"]

# qtviz step vocabulary → Plotly line shapes ([D84]).
_LINE_SHAPE = {"pre": "vh", "mid": "hvh", "post": "hv"}
_ARROWSIDE = {"end": "end", "both": "end+start", "none": "none"}
_YANCHOR = {"center": "middle", "top": "top", "bottom": "bottom"}


def _pairs_to_gapped(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(x) // 2
    gap = np.full(n, np.nan)
    gx = np.column_stack([x[0::2], x[1::2], gap]).ravel()
    gy = np.column_stack([y[0::2], y[1::2], gap]).ravel()
    return gx, gy


def polyline_ops(m: Polyline, name: str) -> list[Op]:
    x, y = (m.x, m.y) if m.connect == "finite" else _pairs_to_gapped(m.x, m.y)
    line: dict = {"color": _css(m.stroke.color), "width": m.stroke.width,
                  "dash": _dash(m.stroke.dash)}
    if m.step is not None:
        line["shape"] = _LINE_SHAPE[m.step]
    trace: dict = {"type": "scattergl", "mode": "lines", "x": x, "y": y,
                   "line": line, "opacity": m.stroke.alpha, "hoverinfo": "skip",
                   "name": name, "showlegend": False}
    if m.fill_to is not None:
        trace["fill"] = "tozeroy"
    return [("trace", trace)]


def markers_ops(m: Markers, name: str) -> list[Op]:
    if isinstance(m.fill, np.ndarray):
        color: object = [_rgba_css_row(row) for row in m.fill]
    else:
        color = _css(m.fill) if m.fill is not None else None
    trace = {"type": "scattergl", "mode": "markers", "x": m.x, "y": m.y,
             "marker": {"color": color, "size": m.size, "symbol": _SYMBOL[m.marker]},
             "opacity": m.alpha, "name": name, "showlegend": False,
             "_legend_target": True}
    return [("trace", trace)]


def _rgba_css_row(row) -> str:
    r, g, b, a = (float(v) for v in row)
    return f"rgba({round(r * 255)}, {round(g * 255)}, {round(b * 255)}, {a:.3g})"


def band_ops(m: Band, name: str) -> list[Op]:
    """Two width-0 line traces; the second fills to the first ([D99] both
    orientations). The filled trace is the legend sample (`_legend_target`)."""
    css = _css(m.fill.color)
    common = {"type": "scatter", "mode": "lines",
              "line": {"width": 0, "color": css}, "name": name}
    fill_css = _rgba_css(m.fill.color, m.fill.alpha)
    if m.orient == "h":
        lo = {**common, "x": m.lo, "y": m.pos,
              "showlegend": False, "hoverinfo": "skip"}
        hi = {**common, "x": m.hi, "y": m.pos, "fill": "tonextx",
              "fillcolor": fill_css, "showlegend": False, "_legend_target": True}
    else:
        lo = {**common, "x": m.pos, "y": m.lo,
              "showlegend": False, "hoverinfo": "skip"}
        hi = {**common, "x": m.pos, "y": m.hi, "fill": "tonexty",
              "fillcolor": fill_css, "showlegend": False, "_legend_target": True}
    return [("trace", lo), ("trace", hi)]


def rule_ops(m: Rule, x_scale: str, y_scale: str) -> list[Op]:
    if m.orient == "slope":
        return [("refline", m)]  # needs the final data span — deferred ([D99])
    axis = "y" if m.orient == "h" else "x"
    pos = _shape_coord(m.at, y_scale if m.orient == "h" else x_scale)
    if pos is None:
        return []
    free = "x" if axis == "y" else "y"
    return [("shape", {
        "type": "line",
        f"{free}ref": "paper", f"{free}0": 0.0, f"{free}1": 1.0,
        f"{axis}ref": axis, f"{axis}0": pos, f"{axis}1": pos,
        "opacity": m.stroke.alpha,
        "line": {"color": _css(m.stroke.color), "width": m.stroke.width,
                 "dash": _dash(m.stroke.dash)},
    })]


def span_ops(m: SpanMark, x_scale: str, y_scale: str) -> list[Op]:
    axis = "y" if m.orient == "h" else "x"
    scale = y_scale if axis == "y" else x_scale
    lo, hi = _shape_coord(m.lo, scale), _shape_coord(m.hi, scale)
    if lo is None or hi is None:
        return []
    free = "x" if axis == "y" else "y"
    return [("shape", {
        "type": "rect",
        f"{free}ref": "paper", f"{free}0": 0.0, f"{free}1": 1.0,
        f"{axis}ref": axis, f"{axis}0": lo, f"{axis}1": hi,
        "fillcolor": _css(m.fill.color), "opacity": m.fill.alpha,
        "line": {"width": 0},
    })]


def text_ops(m: TextMark, theme, x_scale: str, y_scale: str, name: str) -> list[Op]:
    x, y = _shape_coord(m.x, x_scale), _shape_coord(m.y, y_scale)
    if x is None or y is None:
        return []
    font: dict = {"color": _css(m.color)}
    if m.size is not None:
        font["size"] = m.size
    note = {"x": x, "y": y, "text": m.text.replace("\n", "<br>"),
            "showarrow": False, "font": font, "xanchor": m.anchor,
            "yanchor": _YANCHOR[m.anchor_v],
            "textangle": -m.rotation,  # Plotly rotates clockwise ([D96] flip)
            "xref": "x", "yref": "y"}
    if m.frame:
        note.update(bordercolor=_css(m.color), borderwidth=1,
                    bgcolor=_css(theme.background), borderpad=3)
    ops: list[Op] = [("note", note)]
    if m.mask is not None:  # [D117] line break under the label
        x0, y0, x1, y1 = m.mask
        ops.append(("trace", {
            "type": "scattergl", "mode": "lines",
            "x": np.array([x0, x1]), "y": np.array([y0, y1]),
            "line": {"color": _css(theme.background), "width": m.mask_width},
            "hoverinfo": "skip", "name": name, "showlegend": False,
        }))
    return ops


def polygon_ops(m: PolygonMark, x_scale: str, y_scale: str) -> list[Op]:
    from ...core._geometry import svg_path  # noqa: PLC0415

    xs = [_shape_coord(float(v), x_scale) for v in m.x]
    ys = [_shape_coord(float(v), y_scale) for v in m.y]
    if any(v is None for v in xs) or any(v is None for v in ys):
        return []
    shape: dict = {"type": "path", "path": svg_path(list(zip(xs, ys, strict=True))),
                   "xref": "x", "yref": "y"}
    if m.stroke is not None:
        shape["opacity"] = m.stroke.alpha
        shape["line"] = {"color": _css(m.stroke.color), "width": m.stroke.width}
    if m.fill is not None:
        shape.setdefault("opacity", m.fill.alpha)
        shape["fillcolor"] = _css(m.fill.color)
    return [("shape", shape)]


def arrow_ops(m: ArrowMark, x_scale: str, y_scale: str) -> list[Op]:
    x1, y1 = _shape_coord(m.x1, x_scale), _shape_coord(m.y1, y_scale)
    x0, y0 = _shape_coord(m.x0, x_scale), _shape_coord(m.y0, y_scale)
    if None in (x0, y0, x1, y1):
        return []
    return [("note", {
        "x": x1, "y": y1, "ax": x0, "ay": y0,
        "axref": "x", "ayref": "y", "text": "", "showarrow": True,
        "arrowhead": 2, "arrowside": _ARROWSIDE[m.head],
        "arrowcolor": _css(m.stroke.color),
        "arrowwidth": max(m.stroke.width, 0.3),
        "opacity": m.stroke.alpha,
    })]


def lowered_ops(lowered, element, theme, x_scale: str, y_scale: str) -> list[Op]:
    """All ops for one lowered element, legend behavior preserved: the entry
    rides the trace flagged `_legend_target` (a Band's filled trace, a
    Markers trace — Stem's head sample, [D115]) when one exists, else the
    first trace (Quiver/Streamlines); an `"arrow"`-glyph entry ([D112]
    reference key) becomes a legend-only null trace like pre-IR."""
    name = element.id
    ops: list[Op] = []
    marker_trace: dict | None = None
    first_trace: dict | None = None
    for mark in lowered.marks:
        if isinstance(mark, Polyline):
            mark_ops = polyline_ops(mark, name)
        elif isinstance(mark, Band):
            mark_ops = band_ops(mark, name)
        elif isinstance(mark, Markers):
            mark_ops = markers_ops(mark, name)
        elif isinstance(mark, Rule):
            mark_ops = rule_ops(mark, x_scale, y_scale)
        elif isinstance(mark, SpanMark):
            mark_ops = span_ops(mark, x_scale, y_scale)
        elif isinstance(mark, TextMark):
            mark_ops = text_ops(mark, theme, x_scale, y_scale, name)
        elif isinstance(mark, PolygonMark):
            mark_ops = polygon_ops(mark, x_scale, y_scale)
        elif isinstance(mark, ArrowMark):
            mark_ops = arrow_ops(mark, x_scale, y_scale)
        else:  # pragma: no cover — the total-drawer guard keeps this dead
            raise TypeError(f"webengine cannot draw mark {type(mark).__name__}")
        for kind, payload in mark_ops:
            if kind == "trace" and isinstance(payload, dict):
                if first_trace is None:
                    first_trace = payload
                if payload.pop("_legend_target", False) and marker_trace is None:
                    marker_trace = payload  # preferred legend sample
                if isinstance(mark, Markers) and marker_trace is None:
                    marker_trace = payload
            ops.append((kind, payload))
    entry = lowered.legend
    if entry is not None:
        if getattr(entry, "glyph", "swatch") == "arrow":  # [D112] key
            ops.append(("trace", {
                "type": "scattergl", "mode": "lines", "x": [None], "y": [None],
                "line": (first_trace or {}).get("line", {}),
                "name": entry.label, "showlegend": True, "hoverinfo": "skip",
            }))
        else:
            target = marker_trace or first_trace
            if target is not None:
                target["name"] = entry.label
                target["showlegend"] = True
    return ops
