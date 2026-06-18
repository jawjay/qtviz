"""Dynamic viewport-driven re-aggregation (Phase 4b, D21).

The static datashader path (4a) renders one raster at the initial extent; zooming
in just scales that image (it pixelates). This module re-aggregates the **source**
to the visible viewport at the widget's pixel resolution as the user pans/zooms,
so the raster sharpens instead of blurring.

The loop is backend-agnostic but Qt-coupled (it lives in the GUI event loop):
`RasterController` owns the debounce timer, the off-thread aggregation pass, and
stale-result dropping. The only per-backend piece is a tiny `RasterTarget` that
reads the viewport + pixel size and writes the new raster back into the native
image primitive — one small impl per backend, no datashader knowledge required.

`rasterize` is injected (not imported) so this module stays free of any datashader
dependency: a backend hands in `ext.datashader.rasterize_scatter`.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from .disposable import Disposable

# ((x0, x1), (y0, y1)) in data coordinates
Viewport = tuple[tuple[float, float], tuple[float, float]]

_pool: ThreadPoolExecutor | None = None


def _raster_pool() -> ThreadPoolExecutor:
    """Shared worker pool for re-aggregation (kept off the GUI thread)."""
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qtviz-raster")
    return _pool


@runtime_checkable
class RasterTarget(Protocol):
    """The per-backend seam between the controller and a native image primitive.

    `connect_viewport(cb)` must call `cb()` whenever the user pans/zooms and
    return a `Disposable` that unsubscribes. `set_raster` must not itself trigger
    that callback (or must suppress it) to avoid a feedback loop.
    """

    def viewport(self) -> Viewport | None: ...
    def pixel_size(self) -> tuple[int, int]: ...
    def set_raster(self, rgba, bounds) -> None: ...
    def connect_viewport(self, cb: Callable[[], None]) -> Disposable: ...


class RasterController(QObject):
    """Re-aggregates `source` to the target's viewport at its pixel size, off the
    GUI thread, debounced. A monotonic build-id drops stale results so a fast pan
    that supersedes an in-flight aggregation never paints an out-of-date raster.
    """

    _done = Signal(int, object, object)  # build_id, RasterResult | None, exc | None

    def __init__(
        self,
        *,
        source,
        target: RasterTarget,
        rasterize: Callable,  # (source, *, width, height, x_range, y_range) -> RasterResult
        parent: QObject | None = None,
        debounce_ms: int = 100,
        on_aggregate: Callable | None = None,  # called (GUI thread) with each fresh aggregate
        on_legend: Callable | None = None,  # called (GUI thread) with each fresh Legend (C3)
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._target = target
        self._rasterize = rasterize
        self._on_aggregate = on_aggregate
        self._on_legend = on_legend
        self._build_id = 0
        self._disposed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._fire)
        self._done.connect(self._on_done)
        self._sub: Disposable | None = target.connect_viewport(self._schedule)
        self._schedule()  # render once at the true widget resolution

    def _schedule(self) -> None:
        if not self._disposed:
            self._timer.start()  # debounce: each viewport change restarts the countdown

    def _fire(self) -> None:
        vp = self._target.viewport()
        width, height = self._target.pixel_size()
        if vp is None or width <= 0 or height <= 0:
            return  # not laid out yet — a later viewport change will re-trigger
        (x0, x1), (y0, y1) = vp
        self._build_id += 1
        build_id = self._build_id
        source, rasterize = self._source, self._rasterize

        def work():
            return rasterize(
                source, width=int(width), height=int(height),
                x_range=(x0, x1), y_range=(y0, y1),
            )

        _raster_pool().submit(self._run, build_id, work)

    def _run(self, build_id: int, work) -> None:
        try:
            self._done.emit(build_id, work(), None)
        except Exception as e:  # noqa: BLE001
            self._done.emit(build_id, None, e)

    @Slot(int, object, object)
    def _on_done(self, build_id: int, result, exc) -> None:
        if self._disposed or build_id != self._build_id:
            return  # torn down, or a newer pan superseded this aggregation
        if exc is not None:
            return  # keep the current raster on failure
        self._target.set_raster(result.rgba, result.bounds)
        if self._on_aggregate is not None:
            self._on_aggregate(result.aggregate)  # keep hover/inspect values fresh ([D46])
        if self._on_legend is not None and getattr(result, "legend", None) is not None:
            self._on_legend(result.legend)  # refresh legend (vmin/vmax shifts on zoom, C3)

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._timer.stop()
        if self._sub is not None:
            self._sub.dispose()
            self._sub = None
