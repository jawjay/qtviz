"""matplotlib RasterTarget — the per-backend seam for dynamic datashading (4b).

Reads the Axes' data limits + on-screen pixel size and rewrites the AxesImage's
data + extent. `AxesImage.set_extent` can mutate the axes limits (autoscale),
which would re-enter the viewport callback — so set_raster suppresses the
callback while it updates.
"""

from __future__ import annotations

from ...core.disposable import Disposable


def wire_raster_hover(ax, source_id: str, bus, holder) -> Disposable:
    """Emit a `HoverEvent` with the aggregated value under the cursor for a
    datashaded raster ([D46]). `holder.aggregate` is refreshed by the controller on
    pan/zoom; delivery rides the HoverEvent throttle."""
    from ...core.event import HoverEvent  # noqa: PLC0415

    canvas = ax.figure.canvas

    def on_move(event) -> None:
        agg = getattr(holder, "aggregate", None)
        if agg is None or event.inaxes is not ax or event.xdata is None:
            return
        x, y = float(event.xdata), float(event.ydata)
        bus.emit(HoverEvent(source_id, None, x, y, agg.value_at(x, y)))

    cid = canvas.mpl_connect("motion_notify_event", on_move)
    return Disposable(lambda: canvas.mpl_disconnect(cid))


class MplRasterTarget:
    def __init__(self, image, ax) -> None:
        self._image = image
        self._ax = ax
        self._suppress = False

    def viewport(self):
        return tuple(self._ax.get_xlim()), tuple(self._ax.get_ylim())

    def pixel_size(self) -> tuple[int, int]:
        bbox = self._ax.get_window_extent()  # device px of the axes area
        return int(bbox.width), int(bbox.height)

    def set_raster(self, rgba, bounds) -> None:
        from matplotlib.transforms import Bbox  # noqa: PLC0415

        x0, y0, x1, y1 = bounds
        ax = self._ax
        self._suppress = True
        # The raster tracks the viewport, so it must not steer it (P2 drift bug):
        # with autoscale on, set_extent snaps the limits to the raster's
        # pixel-center extent (a slow zoom-in), and its update_datalim call
        # would feed later autoscales. Disable autoscale around the update and
        # restore dataLim — the [D95] selector fix is precedent.
        autox, autoy = ax.get_autoscalex_on(), ax.get_autoscaley_on()
        saved_datalim = Bbox(ax.dataLim.get_points().copy())
        try:
            ax.set_autoscalex_on(False)
            ax.set_autoscaley_on(False)
            self._image.set_data(rgba)
            self._image.set_extent((x0, x1, y0, y1))
        finally:
            ax.dataLim.set(saved_datalim)
            ax.set_autoscalex_on(autox)
            ax.set_autoscaley_on(autoy)
            self._suppress = False
        self._ax.figure.canvas.draw_idle()

    def connect_viewport(self, cb) -> Disposable:
        def on_lim(_ax) -> None:
            if not self._suppress:
                cb()

        cid_x = self._ax.callbacks.connect("xlim_changed", on_lim)
        cid_y = self._ax.callbacks.connect("ylim_changed", on_lim)
        ax = self._ax

        def teardown() -> None:
            ax.callbacks.disconnect(cid_x)
            ax.callbacks.disconnect(cid_y)

        return Disposable(teardown)
