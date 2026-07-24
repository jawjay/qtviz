"""matplotlib native events → typed qtviz events (spec §4.2).

matplotlib is the "static + slow-interactive" backend (native-pivot §2b):
range (axes lim callbacks) and pick (PathCollection picker) are wired here;
brush is programmatic via `MplRenderHandle.select_bounds` (capability
`brush="approximate"`). All deliveries go through the shared EventBus.
"""
# mypy: disable-error-code="attr-defined"

from __future__ import annotations

import numpy as np

from ...core.event import PickEvent, RangeEvent
from ...elements import Curve, Scatter


def connect_range(ax, surface_id: str, bus) -> None:
    def on_lim(_ax) -> None:
        (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
        bus.emit(RangeEvent(surface_id, (x0, x1), (y0, y1)))

    ax.callbacks.connect("xlim_changed", on_lim)
    ax.callbacks.connect("ylim_changed", on_lim)


def wire_pick(artist, source_id: str, bus) -> None:
    artist.set_picker(True)
    offsets = np.asarray(artist.get_offsets())

    def on_pick(event) -> None:
        if event.artist is not artist or not len(event.ind):
            return
        i = int(event.ind[0])
        x, y = (float(offsets[i][0]), float(offsets[i][1])) if i < len(offsets) else (0.0, 0.0)
        bus.emit(PickEvent(source_id, i, x, y))

    artist.figure.canvas.mpl_connect("pick_event", on_pick)


def attach(element, artist, ctx, selectables: list) -> None:
    if isinstance(element, (Scatter, Curve)):
        x = np.asarray(element.data.series("x"), dtype="float64")  # resolved role
        y = np.asarray(element.data.series("y"), dtype="float64")
        selectables.append((element.id, x, y))
    from ..pyqtgraph._events import raster_source_xy  # noqa: PLC0415 — shared [D78] rule

    raster = raster_source_xy(element)
    if raster is not None:
        selectables.append(raster)  # brush a datashaded view → source rows ([D78])
    if isinstance(element, Scatter) and artist is not None and hasattr(artist, "get_offsets"):
        wire_pick(artist, element.id, ctx.event_bus)
