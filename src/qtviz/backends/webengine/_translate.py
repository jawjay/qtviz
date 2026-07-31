"""Webengine bridge messages → qtviz typed events (D27, W3a/W3b).

Pure: a message name + payload (+ the trace→source_id table) in, typed
``Event``s out. The legacy per-library event dataclasses stay an internal detail;
the public stream is qtviz events, so a webengine pane is indistinguishable to
``View.on(...)``. :func:`translate` dispatches by message prefix — ``plotly.*``
for native-element figures and Plotly ``RawFigure``s; ``bokeh.*`` for Bokeh /
HoloViews ``RawFigure``s (HoloViews renders through Bokeh).

Range is stateful — a Plotly relayout often carries only the changed axis — so
:func:`parse_relayout` / :func:`parse_bokeh_ranges` extract what they can and the
RenderHandle merges it against its last-known ranges before emitting a
``RangeEvent``.
"""

from __future__ import annotations

from ...core.event import HoverEvent, PickEvent, SelectEvent, TapEvent


def _src(trace_index, traces, surface_id: str) -> str:
    if trace_index is not None and 0 <= trace_index < len(traces):
        return traces[trace_index]
    return traces[0] if traces else surface_id


def _f(v) -> float:
    """A coordinate as a float; a non-numeric value (e.g. a categorical-axis label
    like a bar's `x="d"`) becomes NaN rather than crashing `float()`."""
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _scalar_index(pi):
    """A single integer row index, or None when there isn't one — a surface /
    heatmap / contour point is a multi-dim `[row, col]` cell (Plotly sends a list),
    not a row index, and a RawFigure has no row identity anyway."""
    if isinstance(pi, bool) or not isinstance(pi, (int, float)):
        return None
    return int(pi)


def _first_point(payload: dict):
    pts = payload.get("points") or []
    return pts[0] if pts else None


def translate(name: str, payload, *, traces: list[str], surface_id: str) -> list:
    """Map a self-contained bridge message to typed events (0, 1, or — for a
    multi-element Plotly selection — N). Dispatches by message prefix; range
    messages (plotly.relayout / bokeh.ranges_update) are handled statefully by
    the RenderHandle, not here."""
    if not isinstance(payload, dict):
        return []
    if name.startswith("bokeh."):
        return _translate_bokeh(name, payload, traces, surface_id)
    return _translate_plotly(name, payload, traces, surface_id)


def _translate_plotly(name: str, payload: dict, traces: list[str], surface_id: str) -> list:
    if name == "plotly.click":
        p = _first_point(payload)
        if p is None:
            return []
        idx = _scalar_index(p.get("point_index"))
        return [PickEvent(_src(p.get("trace_index"), traces, surface_id),
                          idx if idx is not None else -1, _f(p.get("x")), _f(p.get("y")))]

    if name == "plotly.hover":
        p = _first_point(payload)
        if p is None:
            return []
        return [HoverEvent(_src(p.get("trace_index"), traces, surface_id),
                           _scalar_index(p.get("point_index")), _f(p.get("x")), _f(p.get("y")))]

    if name == "plotly.unhover":
        return [HoverEvent(traces[0] if traces else surface_id, None, 0.0, 0.0)]

    if name == "plotly.selection":
        return _selection_events(payload, traces, surface_id)

    return []


def _selection_events(payload: dict, traces: list[str], surface_id: str) -> list:
    """One SelectEvent per source element (matches native pyqtgraph, D27): group
    the selected points by trace → source-id; emit one event per source in trace
    order (empty indices for an unselected source), so linked brushing keeps each
    element's identity."""
    rng = payload.get("range") or {}
    xr = rng.get("x") or (0.0, 0.0)
    yr = rng.get("y") or (0.0, 0.0)
    bounds = (_f(xr[0]), _f(yr[0]), _f(xr[1]), _f(yr[1]))

    by_source: dict[str, list[int]] = {}
    for p in payload.get("points") or []:
        idx = _scalar_index(p.get("point_index"))
        if idx is None:  # skip multi-dim (surface/heatmap) cells — no row identity
            continue
        by_source.setdefault(_src(p.get("trace_index"), traces, surface_id), []).append(idx)

    order: list[str] = []
    for sid in (traces or [surface_id]):
        if sid not in order:
            order.append(sid)
    for sid in by_source:  # a source seen only via points (shouldn't happen, but safe)
        if sid not in order:
            order.append(sid)
    return [SelectEvent(sid, by_source.get(sid, []), bounds) for sid in order]


# ── Bokeh / HoloViews (W3b) ───────────────────────────────────────────────────
def _translate_bokeh(name: str, payload: dict, traces: list[str], surface_id: str) -> list:
    """Bokeh events for a Bokeh/HoloViews RawFigure. The whole figure is one
    source (its own id, `traces[0]`); tap/range are surface-level. A Bokeh
    SelectionGeometry carries the brushed *region*, not row indices (those live
    in the glyph's data source), so SelectEvent gets bounds with empty indices."""
    source_id = traces[0] if traces else surface_id
    kind = name.split(".", 1)[1]
    if kind == "tap":
        return [TapEvent(surface_id, _f(payload.get("x")), _f(payload.get("y")))]
    if kind == "selection":
        return [SelectEvent(source_id, [], _bokeh_geometry_bounds(payload.get("geometry")))]
    # double_tap has no qtviz equivalent; ranges_update is handled by the handle.
    return []


def _bokeh_geometry_bounds(geometry) -> tuple[float, float, float, float]:
    if not isinstance(geometry, dict):
        return (0.0, 0.0, 0.0, 0.0)
    if geometry.get("type") == "rect":
        return (_f(geometry.get("x0")), _f(geometry.get("y0")),
                _f(geometry.get("x1")), _f(geometry.get("y1")))
    if geometry.get("type") == "point":
        x, y = _f(geometry.get("x")), _f(geometry.get("y"))
        return (x, y, x, y)
    if geometry.get("type") == "poly":  # lasso → bounding box
        xs = [v for v in (geometry.get("x") or []) if v is not None]
        ys = [v for v in (geometry.get("y") or []) if v is not None]
        if xs and ys:
            return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))
    return (0.0, 0.0, 0.0, 0.0)


def parse_bokeh_ranges(payload):
    """A bokeh.ranges_update payload {x0,x1,y0,y1} → (x_range | None, y_range | None)."""
    if not isinstance(payload, dict):
        return None, None
    try:
        x0, x1, y0, y1 = (payload.get(k) for k in ("x0", "x1", "y0", "y1"))
        x = (float(x0), float(x1)) if x0 is not None and x1 is not None else None
        y = (float(y0), float(y1)) if y0 is not None and y1 is not None else None
    except (TypeError, ValueError):
        return None, None
    return x, y


def _range_value(v) -> float:
    """One relayout range endpoint → data space: floats pass through; a date
    axis reports ISO strings, parsed to canonical epoch seconds ([D94])."""
    if isinstance(v, str):
        import numpy as np  # noqa: PLC0415

        return float(np.datetime64(v).astype("datetime64[ms]").astype("int64")) / 1000.0
    return float(v)


def _axis_range(update: dict, prefix: str):
    try:
        lo = update.get(f"{prefix}.range[0]")
        hi = update.get(f"{prefix}.range[1]")
        if lo is not None and hi is not None:
            return (_range_value(lo), _range_value(hi))
        r = update.get(f"{prefix}.range")
        if isinstance(r, (list, tuple)) and len(r) == 2:
            return (_range_value(r[0]), _range_value(r[1]))
    except (TypeError, ValueError):
        return None  # unparseable axis payload
    return None


def parse_relayout(update):
    """A Plotly relayout update → (x_range | None, y_range | None)."""
    if not isinstance(update, dict):
        return None, None
    return _axis_range(update, "xaxis"), _axis_range(update, "yaxis")
