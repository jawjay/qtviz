"""Native pyqtgraph signal → typed qtviz event wiring (milestone M4).

Pick/hover are element-level events (carry the Element id); range/select/tap
are surface-level (handled by the QtvizViewBox, _interaction.py). `attach`
is the single dispatch the renderer calls per element.
"""

from __future__ import annotations

import numpy as np

from ...core.event import HoverEvent, PickEvent
from ...elements import Curve, Scatter


def wire_scatter(item, source_id: str, bus) -> None:
    """Connect a ScatterPlotItem's click/hover to typed events.
    pyqtgraph's signals are `(item, points, ev)` (3-arg)."""

    def on_click(_it, points, _ev) -> None:
        if points is not None and len(points):
            sp = points[0]
            p = sp.pos()
            bus.emit(PickEvent(source_id, int(sp.index()), float(p.x()), float(p.y())))

    def on_hover(_it, points, _ev) -> None:
        if points is not None and len(points):
            sp = points[0]
            p = sp.pos()
            bus.emit(HoverEvent(source_id, int(sp.index()), float(p.x()), float(p.y())))
        else:
            bus.emit(HoverEvent(source_id, None, 0.0, 0.0))

    item.sigClicked.connect(on_click)
    if hasattr(item, "sigHovered"):
        item.sigHovered.connect(on_hover)


def attach(element, item, ctx) -> None:
    """Wire interaction for a rendered element: register it as brush-selectable
    and (for scatters) connect pick/hover."""
    vb = ctx.parent_axes.getViewBox()
    if isinstance(element, (Scatter, Curve)) and hasattr(vb, "add_selectable"):
        x = np.asarray(element.data.series(element.x), dtype="float64")
        y = np.asarray(element.data.series(element.y), dtype="float64")
        vb.add_selectable(element.id, x, y)
    if isinstance(element, Scatter) and item is not None and hasattr(item, "sigClicked"):
        wire_scatter(item, element.id, ctx.event_bus)
