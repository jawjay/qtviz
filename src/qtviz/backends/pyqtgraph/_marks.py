"""Mark drawers — the pyqtgraph [D122] adapter.

One function per mark type, written once; `render_lowered` is the generic
renderer the backend dispatches to for any element whose `lower()` is
overridden and that has no native fast-path registration. Marks arrive in
linear data space ([D121]); the log pretransform (`logify`, incl. its
non-positive warn-drop policy) is applied HERE — the one place pyqtgraph's
Approach-A log handling now lives for lowered elements. Angles are CCW
degrees ([D96]); pg's TextItem angle is CCW too, so no sign flip.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pyqtgraph as pg

from ...core._scales import logify
from ...core.lowering import LowerContext
from ...core.marks import (
    MARK_TYPES,
    ArrowMark,
    Band,
    Markers,
    PolygonMark,
    Polyline,
    Rule,
    SpanMark,
    TextMark,
)
from ._events import wire_scatter

# qtviz marker vocabulary → pg symbols (kept in sync with _renderers._MARKER).
from ._renderers import _MARKER, _mk_pen


def _xy_log(ctx) -> tuple[bool, bool]:
    return ctx.x_scale == "log", ctx.y_scale == "log"


def _qcolor(color, alpha: float):
    qc = color.qt()
    qc.setAlphaF(qc.alphaF() * alpha)
    return qc


def _scalar(value: float, is_log: bool) -> float | None:
    """One coordinate through the axis scale (R1): `None` (drop, logify already
    warned) when non-positive under log makes it non-finite."""
    v = logify(np.array([value], dtype="float64"), is_log)[0]
    return float(v) if np.isfinite(v) else None


# qtviz step vocabulary → pg stepMode ("left" holds each value rightward —
# the post-step; pre-IR Ecdf used exactly this).
_STEPMODE = {"post": "left", "pre": "right", "mid": "center"}


def draw_polyline(m: Polyline, ctx):
    x_log, y_log = _xy_log(ctx)
    pen = _mk_pen(_qcolor(m.stroke.color, m.stroke.alpha), m.stroke.width, m.stroke.dash)
    kwargs: dict = {}
    if m.step is not None:
        kwargs["stepMode"] = _STEPMODE[m.step]
    item = pg.PlotCurveItem(x=logify(m.x, x_log), y=logify(m.y, y_log),
                            pen=pen, connect=m.connect, **kwargs)
    ctx.parent_axes.addItem(item)
    return item


def draw_markers(m: Markers, ctx):
    x_log, y_log = _xy_log(ctx)
    color = (m.fill if isinstance(m.fill, np.ndarray)
             else _qcolor(m.fill or ctx.theme.foreground, m.alpha))
    item = pg.ScatterPlotItem(
        x=logify(m.x, x_log), y=logify(m.y, y_log),
        symbol=_MARKER[m.marker], size=m.size, brush=pg.mkBrush(color),
        pen=None if m.edge is None else _mk_pen(
            _qcolor(m.edge.color, m.edge.alpha), m.edge.width, m.edge.dash),
        useCache=True, hoverable=m.pickable)
    ctx.parent_axes.addItem(item)
    return item


def draw_band(m: Band, ctx):
    x_log, y_log = _xy_log(ctx)
    if m.orient == "h":  # ([D99]) band spans x as a function of y
        y = logify(m.pos, y_log)
        lo = pg.PlotDataItem(logify(m.lo, x_log), y)
        hi = pg.PlotDataItem(logify(m.hi, x_log), y)
    else:
        x = logify(m.pos, x_log)
        lo = pg.PlotDataItem(x, logify(m.lo, y_log))
        hi = pg.PlotDataItem(x, logify(m.hi, y_log))
    fill = pg.FillBetweenItem(lo, hi, brush=pg.mkBrush(_qcolor(m.fill.color, m.fill.alpha)))
    for it in (lo, hi, fill):
        ctx.parent_axes.addItem(it)
    return fill


def draw_rule(m: Rule, ctx):
    x_log, y_log = _xy_log(ctx)
    pen = _mk_pen(_qcolor(m.stroke.color, m.stroke.alpha), m.stroke.width, m.stroke.dash)
    if m.orient == "slope":
        # [D99]: a straight data-space line has no log form — warn and drop.
        if ctx.x_scale == "log" or ctx.y_scale == "log":
            import warnings  # noqa: PLC0415

            from ...errors import QtvizWarning  # noqa: PLC0415

            warnings.warn("pyqtgraph: RefLine is a straight data-space line and "
                          "has no log-scale form; it was dropped.",
                          QtvizWarning, stacklevel=2)
            return None
        item = pg.InfiniteLine(pos=(0.0, m.at),
                               angle=math.degrees(math.atan(m.slope or 0.0)),
                               pen=pen, movable=False)
    else:
        pos = _scalar(m.at, y_log if m.orient == "h" else x_log)
        if pos is None:
            return None
        item = pg.InfiniteLine(pos=pos, angle=0 if m.orient == "h" else 90,
                               pen=pen, movable=False)
    ctx.parent_axes.addItem(item)
    return item


def draw_span(m: SpanMark, ctx):
    x_log, y_log = _xy_log(ctx)
    is_h = m.orient == "h"
    lo = _scalar(m.lo, y_log if is_h else x_log)
    hi = _scalar(m.hi, y_log if is_h else x_log)
    if lo is None or hi is None:
        return None
    item = pg.LinearRegionItem(
        values=(lo, hi), orientation="horizontal" if is_h else "vertical",
        movable=False, brush=pg.mkBrush(_qcolor(m.fill.color, m.fill.alpha)),
        pen=pg.mkPen(None))
    ctx.parent_axes.addItem(item)
    return item


_ANCHOR_H = {"center": 0.5, "left": 0.0, "right": 1.0}
_ANCHOR_V = {"center": 0.5, "top": 0.0, "bottom": 1.0}


def draw_text(m: TextMark, ctx):
    x_log, y_log = _xy_log(ctx)
    px, py = _scalar(m.x, x_log), _scalar(m.y, y_log)
    if px is None or py is None:
        return None
    fg = m.color.qt()
    kwargs: dict = {
        "color": fg,
        "anchor": (_ANCHOR_H[m.halign], _ANCHOR_V[m.valign]),
        "angle": m.rotation,  # CCW degrees — pg matches [D96] directly
    }
    if m.frame:
        kwargs["border"] = pg.mkPen(fg)
        kwargs["fill"] = pg.mkBrush(ctx.theme.background.qt())
    item = pg.TextItem(m.text, **kwargs)
    if m.size is not None:
        font = item.textItem.font()
        font.setPointSizeF(float(m.size))
        item.setFont(font)
    ctx.parent_axes.addItem(item)
    item.setPos(px, py)
    if m.mask is not None:  # [D117] contour-label line break
        x0, y0, x1, y1 = m.mask
        mask_pen = pg.mkPen(ctx.theme.background.qt(), width=m.mask_width)
        mask = pg.PlotCurveItem(x=logify(np.array([x0, x1]), x_log),
                                y=logify(np.array([y0, y1]), y_log), pen=mask_pen)
        mask.setZValue(item.zValue() - 1)
        ctx.parent_axes.addItem(mask)
        return [mask, item]
    return item


def draw_polygon(m: PolygonMark, ctx):
    """One closed outline as a path item ([D97]): points logify like every
    annotation; any non-finite point under log drops the shape (logify already
    warned)."""
    from PySide6.QtWidgets import QGraphicsPathItem  # noqa: PLC0415

    x_log, y_log = _xy_log(ctx)
    xs, ys = logify(m.x, x_log), logify(m.y, y_log)
    if not (np.isfinite(xs).all() and np.isfinite(ys).all()):
        return None
    item = QGraphicsPathItem(pg.arrayToQPath(xs, ys))
    if m.stroke is not None:
        item.setPen(_mk_pen(_qcolor(m.stroke.color, m.stroke.alpha),
                            m.stroke.width, m.stroke.dash))
    item.setBrush(pg.mkBrush(_qcolor(m.fill.color, m.fill.alpha))
                  if m.fill is not None else pg.mkBrush(None))
    ctx.parent_axes.addItem(item)
    return item


def draw_arrow(m: ArrowMark, ctx):
    """Shaft as a curve, pixel-mode heads via `ArrowItem` ([D96]) — the pg
    arrow primitive, exactly the pre-IR construction."""
    x_log, y_log = _xy_log(ctx)
    x0, y0 = _scalar(m.x0, x_log), _scalar(m.y0, y_log)
    x1, y1 = _scalar(m.x1, x_log), _scalar(m.y1, y_log)
    if x0 is None or y0 is None or x1 is None or y1 is None:
        return None
    color = _qcolor(m.stroke.color, m.stroke.alpha)
    pen = pg.mkPen(color, width=m.stroke.width)
    shaft = pg.PlotCurveItem(x=np.array([x0, x1]), y=np.array([y0, y1]), pen=pen)
    ctx.parent_axes.addItem(shaft)
    items = [shaft]
    theta = math.degrees(math.atan2(y1 - y0, x1 - x0))
    head_len = 6.0 + 3.0 * m.stroke.width
    heads = {"end": ((x1, y1, 180.0 - theta),),
             "both": ((x1, y1, 180.0 - theta), (x0, y0, -theta)),
             "none": ()}[m.head]
    for hx, hy, angle in heads:
        head = pg.ArrowItem(pos=(hx, hy), angle=angle, headLen=head_len,
                            brush=pg.mkBrush(color), pen=None, pxMode=True)
        ctx.parent_axes.addItem(head)
        items.append(head)
    return items


MARK_DRAWERS = {
    Polyline: draw_polyline,
    Band: draw_band,
    Markers: draw_markers,
    Rule: draw_rule,
    SpanMark: draw_span,
    TextMark: draw_text,
    PolygonMark: draw_polygon,
    ArrowMark: draw_arrow,
}

# Band / Rects arrive with the wave-3 stats lowerings; until then the guard
# below only requires the types wave-2 elements emit.
UNDRAWN = tuple(t for t in MARK_TYPES if t not in MARK_DRAWERS)


def render_lowered(element, ctx):
    """The generic renderer for lowered elements: lower once, draw each mark,
    wire declared pickability/selection ([D124]). Surface-level legend
    aggregation (`legend_entry()` in `_render_cell`) is untouched — lowering
    re-emits the same entry only for the honesty guard. Data-carrying
    elements also register a [D128] relower entry on the ViewBox so
    `set_element_data` can stream them in place."""
    lower_ctx = LowerContext(theme=ctx.theme,
                             series_index=ctx.series_index,
                             show_legend=ctx.show_legend)
    lowered = element.lower(lower_ctx)
    vb = ctx.parent_axes.getViewBox()
    items = []
    pairs = []  # (mark, single item | None) aligned to lowered.marks ([D128])
    for mark in lowered.marks:
        item = MARK_DRAWERS[type(mark)](mark, ctx)
        pairs.append((mark, None if item is None or isinstance(item, list) else item))
        if item is None:
            continue
        if isinstance(mark, Markers) and mark.pickable and hasattr(item, "sigClicked"):
            wire_scatter(item, element.id, ctx.event_bus, vb)
        items.extend(item) if isinstance(item, list) else items.append(item)
    if getattr(element, "data", None) is not None:  # [D128] streamable
        x_log, y_log = _xy_log(ctx)
        reg = getattr(vb, "_qtviz_lowered", None)
        if reg is None:
            reg = vb._qtviz_lowered = {}
        reg[element.id] = _LoweredEntry(element, lower_ctx, pairs, x_log, y_log)
    if len(items) == 1:
        return items[0]
    return items or None


# ── [D128] streaming through lowering ────────────────────────────────────────
class _LoweredEntry:
    """Per-element relower record on the ViewBox (`_qtviz_lowered`), the
    raster-controller registry pattern: the resolved element, its
    `LowerContext`, the (mark, item) pairs, and the surface's log flags —
    everything `update_lowered` needs to relower and write in place."""

    __slots__ = ("element", "lower_ctx", "marks", "items", "x_log", "y_log")

    def __init__(self, element, lower_ctx, pairs, x_log, y_log) -> None:
        self.element = element
        self.lower_ctx = lower_ctx
        self.marks = tuple(m for m, _ in pairs)
        self.items = tuple(i for _, i in pairs)
        self.x_log, self.y_log = x_log, y_log


def _update_polyline(item, m: Polyline, x_log, y_log) -> None:
    item.setData(x=logify(m.x, x_log), y=logify(m.y, y_log))


def _update_markers(item, m: Markers, x_log, y_log) -> None:
    item.setData(x=logify(m.x, x_log), y=logify(m.y, y_log))


def _update_band(item, m: Band, x_log, y_log) -> None:
    lo_curve, hi_curve = item.curves  # FillBetweenItem refills on curve change
    if m.orient == "h":
        y = logify(m.pos, y_log)
        lo_curve.setData(logify(m.lo, x_log), y)
        hi_curve.setData(logify(m.hi, x_log), y)
    else:
        x = logify(m.pos, x_log)
        lo_curve.setData(x, logify(m.lo, y_log))
        hi_curve.setData(x, logify(m.hi, y_log))


MARK_UPDATERS: dict[type, Callable[[Any, Any, bool, bool], None]] = {
    Polyline: _update_polyline, Markers: _update_markers, Band: _update_band}


def update_lowered(entry: _LoweredEntry, arrays: dict, vb) -> bool:
    """[D128]: relower with the streamed role-keyed `arrays` and write each
    mark item's geometry in place. All-or-nothing — the mark sequence must
    type-match the rendered one and every mark must have an updater and a
    live single item, or nothing is touched and the caller's rebuild
    fallback runs (explicit degradation, [D77])."""
    from ...data import EagerTabularRef  # noqa: PLC0415

    new_el = entry.element._replace_data(EagerTabularRef(arrays, arrays))
    lowered = new_el.lower(entry.lower_ctx)
    if tuple(type(m) for m in lowered.marks) != tuple(type(m) for m in entry.marks):
        return False
    if any(type(m) not in MARK_UPDATERS or item is None
           for m, item in zip(lowered.marks, entry.items, strict=True)):
        return False
    for m, item in zip(lowered.marks, entry.items, strict=True):
        MARK_UPDATERS[type(m)](item, m, entry.x_log, entry.y_log)
    entry.element = new_el
    entry.marks = lowered.marks
    xy = new_el.select_xy()  # brush masks run in data space — keep truthful
    selectables = getattr(vb, "_selectables", None)
    if xy is not None and selectables is not None:
        from ...core._time import as_float_seconds  # noqa: PLC0415

        nx, ny = as_float_seconds(xy[0]), as_float_seconds(xy[1])
        for i, sel in enumerate(selectables):
            if sel[0] == new_el.id:
                selectables[i] = (new_el.id, nx, ny)
    return True
