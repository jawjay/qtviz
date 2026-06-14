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

from ...core.event import RangeEvent, SelectEvent, TapEvent

_SHIFT = Qt.KeyboardModifier.ShiftModifier
_LEFT = Qt.MouseButton.LeftButton


class QtvizViewBox(pg.ViewBox):
    def __init__(self, *, bus, surface_id: str, **kw) -> None:
        super().__init__(**kw)
        self.setMouseMode(pg.ViewBox.PanMode)
        self._bus = bus
        self._surface_id = surface_id
        self._selectables: list[tuple[str, np.ndarray, np.ndarray]] = []
        self.sigRangeChanged.connect(self._on_range)

    # ── selectable registry (populated by renderers via _events.attach) ──
    def add_selectable(self, source_id: str, x: np.ndarray, y: np.ndarray) -> None:
        self._selectables.append((source_id, np.asarray(x), np.asarray(y)))

    def select_bounds(self, xmin: float, ymin: float, xmax: float, ymax: float) -> None:
        """Programmatic brush — also the path the Shift-drag gesture calls.
        Emits one SelectEvent per selectable element with the in-bounds row
        indices (element-id + indices + bounds; refines D8 for selection)."""
        bounds = (float(xmin), float(ymin), float(xmax), float(ymax))
        for source_id, x, y in self._selectables:
            mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
            self._bus.emit(SelectEvent(source_id, np.nonzero(mask)[0].tolist(), bounds))

    # ── range → RangeEvent (surface-level, D8) ──
    def _on_range(self, *_args) -> None:
        (x0, x1), (y0, y1) = self.viewRange()
        self._bus.emit(RangeEvent(self._surface_id, (x0, x1), (y0, y1)))

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
            xmin, xmax = sorted((p1.x(), p2.x()))
            ymin, ymax = sorted((p1.y(), p2.y()))
            self.select_bounds(xmin, ymin, xmax, ymax)

    def mouseClickEvent(self, ev) -> None:
        if ev.button() == _LEFT:
            p = self.mapSceneToView(ev.scenePos())
            self._bus.emit(TapEvent(self._surface_id, float(p.x()), float(p.y())))
        super().mouseClickEvent(ev)
