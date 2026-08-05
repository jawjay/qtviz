"""webengine RasterTarget — the per-backend seam for dynamic datashading (4b).

Closes the webengine gap: datashaded rasters re-aggregate to the visible
viewport at the plot's pixel resolution, like pyqtgraph/matplotlib. The seam is
the `plotly.view` bridge message (axis ranges + plot-area pixel size, sent by
the JS runtime on attach and after every relayout/resize/react); writes go back
as a `Plotly.restyle` of the image trace's PNG `source` + placement.

Orientation contract (probed against the bundled plotly.js, 2026-08-05):
- z-mode places z row 0 at `y0` — the low-y edge on a non-reversed axis, which
  matches the qtviz raster convention (row 0 = ymin, mpl `origin="lower"`).
- source-mode blits the PNG naturally (its first row at the high-y edge), so
  `encode_raster_png` flips the array vertically before encoding.
- An image trace flips the y axis by default; `_figure.build` pins
  `yaxis.autorange: true` so data plots stay y-up.

Autorange discipline (the P2 drift family): a re-aggregated raster always fills
(a half-pixel inside) the viewport, so if autorange keeps re-running against the
raster's own extent every restyle nudges the ranges, which re-triggers
aggregation. The first `set_raster` therefore pins explicit axis ranges
(autorange off). Plotly's double-click reset (a relayout with
`{x,y}axis.autorange: true`) is intercepted and restored to the *home* extent —
the full-data bounds of the initial static raster — matching matplotlib's
"home keeps working" behavior.
"""

from __future__ import annotations

import base64

import numpy as np

from ...core.disposable import Disposable

_VIEW_MSG = "plotly.view"
_RELAYOUT_MSG = "plotly.relayout"


def encode_raster_png(rgba: np.ndarray) -> str:
    """A qtviz raster (row 0 = ymin) → PNG data URI in natural image order
    (first row = ymax), for a Plotly image trace's `source`."""
    from PySide6.QtCore import QBuffer  # noqa: PLC0415
    from PySide6.QtGui import QImage  # noqa: PLC0415

    arr = np.ascontiguousarray(np.flipud(np.asarray(rgba, dtype=np.uint8)))
    h, w = arr.shape[:2]
    img = QImage(arr.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888)
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")  # type: ignore[call-overload]  # stubs say bytes, runtime wants str
    return "data:image/png;base64," + base64.b64encode(buf.data().data()).decode("ascii")


def raster_placement(shape, bounds) -> dict:
    """Image-trace placement attrs for a raster whose `bounds` are treated as
    rect edges (the pg/mpl convention): x0/y0 are the *center* of the first
    pixel, dx/dy the pixel pitch."""
    h, w = shape[0], shape[1]
    x0, y0, x1, y1 = (float(v) for v in bounds)
    dx = (x1 - x0) / max(w, 1)
    dy = (y1 - y0) / max(h, 1)
    return {"x0": x0 + dx / 2.0, "dx": dx, "y0": y0 + dy / 2.0, "dy": dy}


class PlotlyRasterTarget:
    """RasterTarget over the Qt↔JS bridge. Viewport/pixel-size arrive as
    `plotly.view` messages; `set_raster` restyles the image trace in place.
    `home` is the full-data extent restored on a double-click autorange reset."""

    def __init__(self, host, view, trace_index: int, *, home=None) -> None:
        self._host = host
        self._view = view
        self._trace_index = trace_index
        self._home = tuple(float(v) for v in home) if home is not None else None
        self._x_range: tuple[float, float] | None = None
        self._y_range: tuple[float, float] | None = None
        self._px: tuple[int, int] = (0, 0)
        self._cb = None
        self._pinned = False  # explicit ranges sent — autorange no longer steers

    # ── RasterTarget protocol ────────────────────────────────────────────
    def viewport(self):
        if self._x_range is None or self._y_range is None:
            return None
        return self._x_range, self._y_range

    def pixel_size(self) -> tuple[int, int]:
        return self._px

    def set_raster(self, rgba, bounds) -> None:
        if not self._pinned and self._x_range is not None and self._y_range is not None:
            # Pin the axes the first time the loop writes: autorange re-running
            # against the raster's own (half-pixel-inset) extent would nudge the
            # ranges every restyle — the P2 drift family. Ranges equal the
            # current viewport, so nothing moves visibly; the echoed relayout
            # dedups in _on_message.
            self._pinned = True
            self._host.relayout({
                "xaxis.range": list(self._x_range), "yaxis.range": list(self._y_range),
                "xaxis.autorange": False, "yaxis.autorange": False,
            })
        update: dict = {"source": [encode_raster_png(rgba)], "z": [None]}
        for key, value in raster_placement(np.shape(rgba), bounds).items():
            update[key] = [value]
        self._host.restyle(update, [self._trace_index])

    def connect_viewport(self, cb) -> Disposable:
        self._cb = cb
        self._view.received.connect(self._on_message)
        view = self._view

        def teardown() -> None:
            self._cb = None
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(RuntimeError, TypeError):
                view.received.disconnect(self._on_message)

        return Disposable(teardown)

    # ── bridge messages ──────────────────────────────────────────────────
    def _on_message(self, name: str, payload) -> None:
        if name == _RELAYOUT_MSG:
            self._maybe_restore_home(payload)
            return
        if name != _VIEW_MSG or not isinstance(payload, dict):
            return
        x, y = _pair(payload.get("x")), _pair(payload.get("y"))
        w, h = int(payload.get("w") or 0), int(payload.get("h") or 0)
        if x is None or y is None:
            return
        state = (x, y, (w, h))
        if state == (self._x_range, self._y_range, self._px):
            return  # echo of our own pin/restyle — don't re-aggregate
        self._x_range, self._y_range, self._px = state
        if self._cb is not None:
            self._cb()

    def _maybe_restore_home(self, payload) -> None:
        """Double-click reset relayouts `{x,y}axis.autorange: true`; with the
        axes pinned that would recompute from the current raster (≈ the current
        viewport) and go nowhere — restore the full-data extent instead."""
        if self._home is None or not self._pinned:
            return
        update = payload.get("update", {}) if isinstance(payload, dict) else {}
        if not (update.get("xaxis.autorange") or update.get("yaxis.autorange")):
            return
        x0, y0, x1, y1 = self._home
        self._host.relayout({
            "xaxis.range": [x0, x1], "yaxis.range": [y0, y1],
            "xaxis.autorange": False, "yaxis.autorange": False,
        })


def _pair(v) -> tuple[float, float] | None:
    if isinstance(v, (list, tuple)) and len(v) == 2:
        try:
            lo, hi = float(v[0]), float(v[1])
        except (TypeError, ValueError):
            return None
        return (lo, hi)
    return None


def wire_dynamic_rasters(handle, node, theme) -> None:
    """Attach a RasterController per datashaded element in `node` (D21 on
    webengine). Controllers and hover holders land on the handle
    (`_rasters` / `_raster_holders`); `dispose_rasters` tears them down."""
    from types import SimpleNamespace  # noqa: PLC0415

    from ...data.pipeline import raster_aux, resolve_node  # noqa: PLC0415
    from ._figure import _elements, surface_of  # noqa: PLC0415

    surf = surface_of(node)
    for spec in ((surf.x, surf.y) if surf is not None else ()):
        if spec is not None and spec.invert:
            return  # a reversed range would feed datashader descending bounds

    targets = []
    for element in _elements(resolve_node(node)):
        aux = raster_aux(element)
        if aux is None or aux.source is None:
            continue
        if getattr(aux.source, "axis", "y") == "y2":
            continue  # plotly.view reads the primary axes only
        try:
            trace_index = handle._traces.index(element.id)
        except ValueError:
            continue
        targets.append((element, aux, trace_index))
    if not targets:
        return  # keep this path free of the optional datashader import

    from ...core.palette import palettes  # noqa: PLC0415
    from ...core.raster import RasterController  # noqa: PLC0415
    from ...ext.datashader import themed_rasterize  # noqa: PLC0415

    for element, aux, trace_index in targets:
        holder = SimpleNamespace(aggregate=aux.aggregate)
        target = PlotlyRasterTarget(handle._host, handle.widget, trace_index,
                                    home=element.extent)
        controller = RasterController(
            source=aux.source, target=target,
            rasterize=themed_rasterize(theme.palette, palettes.get("viridis"),
                                       _raster_title(aux.source)),
            on_aggregate=lambda agg, h=holder: setattr(h, "aggregate", agg),
        )
        controller.element_id = element.id
        handle._rasters.append(controller)
        handle._raster_holders[element.id] = holder


def _raster_title(source) -> str | None:
    from ...core.encoding import channel_title  # noqa: PLC0415

    color_by = getattr(source, "color_by", None)
    return channel_title(color_by) if color_by is not None else None


def dispose_rasters(handle) -> None:
    for controller in handle._rasters:
        controller.dispose()
    handle._rasters.clear()
    handle._raster_holders.clear()
