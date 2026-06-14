"""pyqtgraph RasterTarget — the per-backend seam for dynamic datashading (4b).

Reads the ViewBox's data-space range + on-screen pixel size, and writes a new
RGBA raster into the ImageItem in place. Updating the image does not change the
view range, so no feedback guard is needed here (cf. the matplotlib target).
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import QRectF

from ...core.disposable import Disposable


class PgRasterTarget:
    def __init__(self, item, view_box) -> None:
        self._item = item
        self._vb = view_box

    def viewport(self):
        (x0, x1), (y0, y1) = self._vb.viewRange()
        return (x0, x1), (y0, y1)

    def pixel_size(self) -> tuple[int, int]:
        rect = self._vb.geometry()  # device-independent px of the plotting area
        return int(rect.width()), int(rect.height())

    def set_raster(self, rgba, bounds) -> None:
        self._item.setImage(rgba, axisOrder="row-major")  # shape may change with px size
        x0, y0, x1, y1 = bounds
        self._item.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))  # after setImage: re-maps new shape

    def connect_viewport(self, cb) -> Disposable:
        def slot(*_args) -> None:
            cb()

        self._vb.sigRangeChanged.connect(slot)
        return Disposable(lambda: _safe_disconnect(self._vb.sigRangeChanged, slot))


def _safe_disconnect(signal, slot) -> None:
    with contextlib.suppress(TypeError, RuntimeError):  # already gone (ViewBox deleted)
        signal.disconnect(slot)
