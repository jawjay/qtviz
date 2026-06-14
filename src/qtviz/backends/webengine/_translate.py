"""Plotly bridge messages → qtviz typed events (D27).

Pure: a message name + payload (+ the trace→source_id table) in, a typed
``Event`` out. The legacy per-library event dataclasses stay an internal detail;
the public stream is qtviz events, so a webengine pane is indistinguishable to
``View.on(...)``.

Self-contained events (click/hover/selection) are mapped by :func:`translate`.
Range is stateful — a relayout often carries only the changed axis — so
:func:`parse_relayout` extracts what it can and the RenderHandle merges it
against its last-known ranges before emitting a ``RangeEvent``.

W1 wires the single-trace case (``point_index`` is the source row index). The
multi-trace ``trace_index → (source_id, row-offset)`` table is D27's
pending-revisit, landing with Overlay selection in W2/W3.
"""

from __future__ import annotations

from ...core.event import HoverEvent, PickEvent, SelectEvent


def _src(trace_index, traces, surface_id: str) -> str:
    if trace_index is not None and 0 <= trace_index < len(traces):
        return traces[trace_index]
    return traces[0] if traces else surface_id


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _first_point(payload: dict):
    pts = payload.get("points") or []
    return pts[0] if pts else None


def translate(name: str, payload, *, traces: list[str], surface_id: str) -> list:
    """Map a self-contained Plotly message to typed events (0, 1, or — for a
    multi-element selection — N)."""
    if not isinstance(payload, dict):
        return []

    if name == "plotly.click":
        p = _first_point(payload)
        if p is None:
            return []
        pi = p.get("point_index")
        return [PickEvent(_src(p.get("trace_index"), traces, surface_id),
                          int(pi) if pi is not None else -1, _f(p.get("x")), _f(p.get("y")))]

    if name == "plotly.hover":
        p = _first_point(payload)
        if p is None:
            return []
        pi = p.get("point_index")
        return [HoverEvent(_src(p.get("trace_index"), traces, surface_id),
                           int(pi) if pi is not None else None, _f(p.get("x")), _f(p.get("y")))]

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
        pi = p.get("point_index")
        if pi is None:
            continue
        by_source.setdefault(_src(p.get("trace_index"), traces, surface_id), []).append(int(pi))

    order: list[str] = []
    for sid in (traces or [surface_id]):
        if sid not in order:
            order.append(sid)
    for sid in by_source:  # a source seen only via points (shouldn't happen, but safe)
        if sid not in order:
            order.append(sid)
    return [SelectEvent(sid, by_source.get(sid, []), bounds) for sid in order]


def _axis_range(update: dict, prefix: str):
    try:
        lo = update.get(f"{prefix}.range[0]")
        hi = update.get(f"{prefix}.range[1]")
        if lo is not None and hi is not None:
            return (float(lo), float(hi))
        r = update.get(f"{prefix}.range")
        if isinstance(r, (list, tuple)) and len(r) == 2:
            return (float(r[0]), float(r[1]))
    except (TypeError, ValueError):
        return None  # non-numeric (e.g. datetime) axis — not wired in W1
    return None


def parse_relayout(update):
    """A Plotly relayout update → (x_range | None, y_range | None)."""
    if not isinstance(update, dict):
        return None, None
    return _axis_range(update, "xaxis"), _axis_range(update, "yaxis")
