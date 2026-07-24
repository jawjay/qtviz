"""Native pyqtgraph signal → typed qtviz event wiring (milestone M4).

Pick/hover are element-level events (carry the Element id); range/select/tap
are surface-level (handled by the QtvizViewBox, _interaction.py). `attach`
is the single dispatch the renderer calls per element.
"""
# mypy: disable-error-code="attr-defined"

from __future__ import annotations

import numpy as np

from ...core.event import HoverEvent, PickEvent
from ...elements import Curve, Image, Scatter


def raster_source_xy(element):
    """The brushable rows of a datashaded Image ([D78]): the SOURCE element's
    resolved x/y when its data is eager (they're in memory anyway), or
    `(source_id, None, None)` for a lazy source — row identity there would
    force a full scan per brush, so only the bounds are emitted."""
    source = getattr(element, "_raster_source", None)
    if not isinstance(element, Image) or source is None:
        return None
    ref = source.data
    if getattr(ref, "is_lazy", False):
        return source.id, None, None
    arrays = ref.resolve_channels({"x": source.x, "y": source.y})
    return source.id, arrays["x"], arrays["y"]


def wire_scatter(item, source_id: str, bus, vb) -> None:
    """Connect a ScatterPlotItem's click/hover to typed events.
    pyqtgraph's signals are `(item, points, ev)` (3-arg). Spot positions are in
    view space — exponent space under log — so coordinates are normalized to data
    space at emit (R1, feasibility §10.3); `sp.index()` is a row index into the
    plotted arrays, which NaN-masking keeps aligned with the source rows."""

    def _data_xy(p) -> tuple[float, float]:
        to_x = getattr(vb, "_to_data_x", float)
        to_y = getattr(vb, "_to_data_y", float)
        return to_x(p.x()), to_y(p.y())

    def on_click(_it, points, _ev) -> None:
        if points is not None and len(points):
            sp = points[0]
            x, y = _data_xy(sp.pos())
            bus.emit(PickEvent(source_id, int(sp.index()), x, y))

    def on_hover(_it, points, _ev) -> None:
        if points is not None and len(points):
            sp = points[0]
            x, y = _data_xy(sp.pos())
            bus.emit(HoverEvent(source_id, int(sp.index()), x, y))
        else:
            bus.emit(HoverEvent(source_id, None, 0.0, 0.0))

    item.sigClicked.connect(on_click)
    if hasattr(item, "sigHovered"):
        item.sigHovered.connect(on_hover)


def attach(element, item, ctx) -> None:
    """Wire interaction for a rendered element: register it as brush-selectable
    (in data space — select masks run there, R1) and (for scatters) connect
    pick/hover."""
    vb = ctx.parent_axes.getViewBox()
    if isinstance(element, (Scatter, Curve)) and hasattr(vb, "add_selectable"):
        x = np.asarray(element.data.series("x"), dtype="float64")  # resolved role
        y = np.asarray(element.data.series("y"), dtype="float64")
        vb.add_selectable(element.id, x, y)
    raster = raster_source_xy(element)
    if raster is not None and hasattr(vb, "add_selectable"):
        vb.add_selectable(*raster)  # brush a datashaded view → source rows ([D78])
    if isinstance(element, Scatter) and item is not None and hasattr(item, "sigClicked"):
        wire_scatter(item, element.id, ctx.event_bus, vb)
