"""matplotlib RasterTarget — the per-backend seam for dynamic datashading (4b).

Reads the Axes' data limits + on-screen pixel size and rewrites the AxesImage's
data + extent. `AxesImage.set_extent` can mutate the axes limits (autoscale),
which would re-enter the viewport callback — so set_raster suppresses the
callback while it updates.
"""

from __future__ import annotations

from ...core.disposable import Disposable


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
        x0, y0, x1, y1 = bounds
        self._suppress = True
        try:
            self._image.set_data(rgba)
            self._image.set_extent((x0, x1, y0, y1))
        finally:
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
