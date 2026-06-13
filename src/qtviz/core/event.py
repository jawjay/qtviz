"""Backend-agnostic typed events (spec §2.10).

The Phase-1 vocabulary. Backends emit only what their `Capabilities` declare.
Events are frozen dataclasses — short-lived carriers, never subclassed by users.
The `EventBus` + throttle (Qt-coupled) land with M4.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .disposable import Disposable

ElementId = str


@dataclass(frozen=True)
class Event:
    source_id: ElementId


@dataclass(frozen=True)
class RangeEvent(Event):
    x: tuple[float, float]
    y: tuple[float, float]


@dataclass(frozen=True)
class PickEvent(Event):
    point_index: int
    x: float
    y: float


@dataclass(frozen=True)
class SelectEvent(Event):
    indices: list[int] = field(default_factory=list)
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class HoverEvent(Event):
    point_index: int | None
    x: float
    y: float


@dataclass(frozen=True)
class TapEvent(Event):
    x: float
    y: float


class _Throttle:
    """Trailing-edge throttle: emit immediately, then at most once per `ms`,
    replaying the latest payload received during the cooldown window. Promoted
    from the webengine code so every backend shares one implementation (§2.10)."""

    def __init__(self, cb: Callable, ms: int) -> None:
        from PySide6.QtCore import QTimer  # noqa: PLC0415

        self._cb = cb
        self._pending = None
        self._has_pending = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._ms = ms

    def submit(self, ev) -> None:
        if not self._timer.isActive():
            self._cb(ev)
            self._timer.start(self._ms)
        else:
            self._pending = ev
            self._has_pending = True

    def _tick(self) -> None:
        if self._has_pending:
            ev, self._pending, self._has_pending = self._pending, None, False
            self._cb(ev)
            self._timer.start(self._ms)


class EventBus:
    """Typed, throttled event delivery. One bus per RenderHandle (§2.10)."""

    DEFAULT_THROTTLE_MS = {
        RangeEvent: 50,
        HoverEvent: 33,
        SelectEvent: 50,
        PickEvent: 0,
        TapEvent: 0,
    }

    def __init__(self) -> None:
        self._subs: dict[type, list] = defaultdict(list)

    def subscribe(
        self,
        event_type: type,
        cb: Callable,
        *,
        throttle_ms: int | None = None,
    ) -> Disposable:
        ms = self.DEFAULT_THROTTLE_MS.get(event_type, 0) if throttle_ms is None else throttle_ms
        sink = _Throttle(cb, ms).submit if ms and ms > 0 else cb
        entry = (cb, sink)
        self._subs[event_type].append(entry)

        def teardown() -> None:
            lst = self._subs.get(event_type)
            if lst and entry in lst:
                lst.remove(entry)

        return Disposable(teardown)

    def emit(self, ev: Event) -> None:
        for _cb, sink in list(self._subs.get(type(ev), ())):
            sink(ev)

    def dispose(self) -> None:
        self._subs.clear()
