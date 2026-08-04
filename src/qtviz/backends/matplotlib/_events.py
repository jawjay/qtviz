"""matplotlib native events → typed qtviz events (spec §4.2).

matplotlib is the "static + slow-interactive" backend (native-pivot §2b):
range (axes lim callbacks), pick (PathCollection picker), and an interactive
rubber-band brush ([D95]) are wired here; `MplRenderHandle.select_bounds`
drives the same masking programmatically (capability `brush="approximate"`).
All deliveries go through the shared EventBus.
"""
# mypy: disable-error-code="attr-defined"

from __future__ import annotations

import numpy as np

from ...core.event import PickEvent, RangeEvent, SelectEvent
from ...elements import Scatter


def emit_bounds_select(selectables, bus, xmin, ymin, xmax, ymax) -> None:
    """One `SelectEvent` per selectable element for a data-space rectangle —
    the shared core of the programmatic `select_bounds` and the interactive
    brush ([D95]). Bounds-only sources ([D78]) emit `indices=[]`."""
    bounds = (float(xmin), float(ymin), float(xmax), float(ymax))
    for source_id, x, y in selectables:
        if x is None:  # bounds-only ([D78]): the bounds ARE the selection
            bus.emit(SelectEvent(source_id, [], bounds))
            continue
        mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
        bus.emit(SelectEvent(source_id, np.nonzero(mask)[0].tolist(), bounds))


def connect_brush(ax, selectables, bus) -> None:
    """Drag-to-select rubber band ([D95]): a `RectangleSelector` whose release
    emits the same SelectEvents as `select_bounds`. Wired only on surfaces with
    brushable elements — the selector parks a rectangle artist on the Axes, so
    it stays off chart types that have nothing to select. The toolbar's
    pan/zoom modes take the widget lock, so the gestures don't fight."""
    from matplotlib.backend_bases import MouseButton  # noqa: PLC0415
    from matplotlib.widgets import RectangleSelector  # noqa: PLC0415

    if not selectables:
        return

    def on_select(eclick, erelease) -> None:
        if eclick.xdata is None or erelease.xdata is None:
            return
        x0, x1 = sorted((eclick.xdata, erelease.xdata))
        y0, y1 = sorted((eclick.ydata, erelease.ydata))
        emit_bounds_select(selectables, bus, x0, y0, x1, y1)

    # The selector parks a 0×0 rectangle at (0, 0) which joins `dataLim` at
    # add time, dragging autoscale out to the origin — a 2026 time series
    # rendered zoomed to 1970 (gallery-audit P1). Snapshot the data limits the
    # rendered elements produced and restore them after (a plain `relim()`
    # would drop collections), then re-run autoscale: the selector's __init__
    # unstales the view limits, so the polluted range is already baked by the
    # time the restore runs. `autoscale_view` is a no-op on axes with explicit
    # limits (set_xlim/ylim turn autoscale off), so `lim=` surfaces are safe.
    from matplotlib.transforms import Bbox  # noqa: PLC0415

    saved = Bbox(ax.dataLim.get_points().copy())
    ax._qtviz_brush = RectangleSelector(  # parked on the Axes to stay alive
        ax, on_select, useblit=False, button=[MouseButton.LEFT], interactive=False,
        minspanx=2, minspany=2, spancoords="pixels",
    )
    ax.dataLim.set(saved)
    ax.autoscale_view()


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
    if getattr(element, "axis", "y") == "y2":
        # y2 rides its own scale; brush bounds are primary-axes data space, so
        # a y2 element is not brush-selectable ([D88]). Pick stays off too —
        # the PathCollection picker reports primary-axes coordinates.
        return
    xy = element.select_xy()  # declared, not isinstance'd ([D124])
    if xy is not None:
        from ...core._time import as_float_seconds  # noqa: PLC0415

        # resolved roles; epoch s ([D94])
        selectables.append((element.id, as_float_seconds(xy[0]), as_float_seconds(xy[1])))
    from ..pyqtgraph._events import raster_source_xy  # noqa: PLC0415 — shared [D78] rule

    raster = raster_source_xy(element)
    if raster is not None:
        selectables.append(raster)  # brush a datashaded view → source rows ([D78])
    if isinstance(element, Scatter) and artist is not None and hasattr(artist, "get_offsets"):
        wire_pick(artist, element.id, ctx.event_bus)
    # (lowered pickable marks — Stem heads [D115] — wire inside render_lowered)
