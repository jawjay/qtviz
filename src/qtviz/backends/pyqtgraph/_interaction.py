"""qtviz interaction model for pyqtgraph (milestone M4, D12).

Rather than layer gestures on top of pyqtgraph's default ViewBox mouse modes
(and fight conflicts between rect-zoom, pan, and our selection), we *own* the
mouse semantics with a ViewBox subclass. One coherent scheme:

    left-drag             → pan        (delegated to pyqtgraph)
    wheel                 → zoom       (delegated to pyqtgraph)
    Shift + left-drag     → rubber-band select → SelectEvent
    left-click (empty)    → TapEvent
    range change          → RangeEvent  (throttled in the EventBus)

Pick / hover on points are wired on the ScatterPlotItem itself (_events.py),
since pyqtgraph already routes point hits there. All events are typed and
published to the EventBus.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt

from ...core._scales import delog
from ...core.event import RangeEvent, SelectEvent, TapEvent

_SHIFT = Qt.KeyboardModifier.ShiftModifier
_LEFT = Qt.MouseButton.LeftButton


class QtvizViewBox(pg.ViewBox):
    """When an axis is log-scaled (`x_log`/`y_log`), the ViewBox — like everything
    pyqtgraph draws — lives in *exponent* space (the renderers pre-`log10` the data,
    Approach A). The R1 rule: every coordinate that leaves this class (events) or
    enters its public API (`select_bounds`) is **data space**; the de-log happens
    exactly once, here at the boundary (feasibility §10.3)."""

    def __init__(self, *, bus, surface_id: str, x_log: bool = False, y_log: bool = False,
                 **kw) -> None:
        super().__init__(**kw)
        self.setMouseMode(pg.ViewBox.PanMode)
        self._bus = bus
        self._surface_id = surface_id
        self.x_log = x_log
        self.y_log = y_log
        self._selectables: list[tuple[str, np.ndarray | None, np.ndarray | None]] = []
        self.sigRangeChanged.connect(self._on_range)

    # ── R1: view (possibly exponent) space → data space ──
    def _to_data_x(self, v: float) -> float:
        return delog(v, self.x_log)

    def _to_data_y(self, v: float) -> float:
        return delog(v, self.y_log)

    # ── selectable registry (populated by renderers via _events.attach) ──
    def add_selectable(self, source_id: str, x, y) -> None:
        """Register brushable rows. `x`/`y` of `None` registers a *bounds-only*
        selectable ([D78]): a brush emits `SelectEvent(source_id, [], bounds)` —
        the predicate form for sources whose row identity would force a compute
        (a lazy datashaded raster)."""
        if x is None or y is None:
            self._selectables.append((source_id, None, None))
        else:
            self._selectables.append((source_id, np.asarray(x), np.asarray(y)))

    def select_bounds(self, xmin: float, ymin: float, xmax: float, ymax: float) -> None:
        """Programmatic brush — also the path the Shift-drag gesture calls.
        Takes and emits **data-space** bounds regardless of axis scale (the
        selectables are stored in data space, so the mask runs there too). Emits
        one SelectEvent per selectable element with the in-bounds row indices
        (element-id + indices + bounds; refines D8 for selection)."""
        bounds = (float(xmin), float(ymin), float(xmax), float(ymax))
        for source_id, x, y in self._selectables:
            if x is None or y is None:  # bounds-only ([D78]): the bounds ARE the selection
                self._bus.emit(SelectEvent(source_id, [], bounds))
                continue
            mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
            self._bus.emit(SelectEvent(source_id, np.nonzero(mask)[0].tolist(), bounds))

    # ── range → RangeEvent (surface-level, D8; R1: emitted in data space) ──
    def _on_range(self, *_args) -> None:
        (x0, x1), (y0, y1) = self.viewRange()
        self._bus.emit(RangeEvent(
            self._surface_id,
            (self._to_data_x(x0), self._to_data_x(x1)),
            (self._to_data_y(y0), self._to_data_y(y1)),
        ))

    # ── mouse ownership ──
    def mouseDragEvent(self, ev, axis=None) -> None:
        if ev.button() == _LEFT and (ev.modifiers() & _SHIFT):
            self._select_drag(ev)
        else:
            super().mouseDragEvent(ev, axis)

    def _select_drag(self, ev) -> None:
        ev.accept()
        self.updateScaleBox(ev.buttonDownPos(), ev.pos())  # rubber-band feedback
        if ev.isFinish():
            self.rbScaleBox.hide()
            p1 = self.mapSceneToView(ev.buttonDownScenePos())
            p2 = self.mapSceneToView(ev.scenePos())
            # view coords are exponent space under log — normalize before masking (R1)
            xmin, xmax = sorted((self._to_data_x(p1.x()), self._to_data_x(p2.x())))
            ymin, ymax = sorted((self._to_data_y(p1.y()), self._to_data_y(p2.y())))
            self.select_bounds(xmin, ymin, xmax, ymax)

    def mouseClickEvent(self, ev) -> None:
        if ev.button() == _LEFT:
            p = self.mapSceneToView(ev.scenePos())
            self._bus.emit(TapEvent(
                self._surface_id, self._to_data_x(p.x()), self._to_data_y(p.y())
            ))
        super().mouseClickEvent(ev)
