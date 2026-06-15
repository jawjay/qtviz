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


def wire_raster_hover(vb, source_id: str, bus, holder) -> Disposable:
    """Emit a `HoverEvent` carrying the aggregated value under the cursor for a
    datashaded raster ([D46]). `holder.aggregate` is the *current* `RasterAggregate`
    (refreshed by the controller on pan/zoom); `value_at` is O(1) and delivery rides
    the HoverEvent throttle, so per-move cost is negligible."""
    from ...core.event import HoverEvent  # noqa: PLC0415

    scene = vb.scene()

    def on_move(scene_pos) -> None:
        agg = getattr(holder, "aggregate", None)
        if agg is None or not vb.sceneBoundingRect().contains(scene_pos):
            return  # outside this view's panel — not our raster
        p = vb.mapSceneToView(scene_pos)
        x, y = float(p.x()), float(p.y())
        bus.emit(HoverEvent(source_id, None, x, y, agg.value_at(x, y)))

    scene.sigMouseMoved.connect(on_move)
    return Disposable(lambda: _safe_disconnect(scene.sigMouseMoved, on_move))


def _safe_disconnect(signal, slot) -> None:
    with contextlib.suppress(TypeError, RuntimeError):  # already gone (ViewBox deleted)
        signal.disconnect(slot)
