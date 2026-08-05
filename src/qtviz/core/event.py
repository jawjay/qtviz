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
    """Base of every typed interaction event. `source_id` names the element
    that emitted it — subscribe with `view.on(EventType, cb)`, optionally
    filtered by element via `source=`."""

    source_id: ElementId


@dataclass(frozen=True)
class RangeEvent(Event):
    """The visible axis ranges changed (pan/zoom): `x`/`y` are the new
    `(lo, hi)` data-space bounds."""

    x: tuple[float, float]
    y: tuple[float, float]


@dataclass(frozen=True)
class PickEvent(Event):
    """A single data point was clicked: its `point_index` in the element's
    data plus the data-space `x`/`y` of the point."""

    point_index: int
    x: float
    y: float


@dataclass(frozen=True)
class SelectEvent(Event):
    """A brush/box selection completed: the selected `indices` into the
    element's data and the data-space `bounds` `(x0, y0, x1, y1)`."""

    indices: list[int] = field(default_factory=list)
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class HoverEvent(Event):
    """The pointer moved over the plot: nearest `point_index` (or `None` off
    the data) and the data-space cursor position. On a datashaded raster
    `value` carries the aggregated count/mean under the cursor."""

    point_index: int | None
    x: float
    y: float
    value: float | None = None


@dataclass(frozen=True)
class TapEvent(Event):
    """A click on empty plot space (no point hit): the data-space `x`/`y` of
    the click."""

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

    def flush(self) -> None:
        """Deliver any coalesced trailing payload immediately (test hook)."""
        if self._has_pending:
            ev, self._pending, self._has_pending = self._pending, None, False
            self._cb(ev)


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
        throttle = _Throttle(cb, ms) if ms and ms > 0 else None
        sink = throttle.submit if throttle is not None else cb
        entry = (sink, throttle)
        self._subs[event_type].append(entry)

        def teardown() -> None:
            lst = self._subs.get(event_type)
            if lst:
                for i, e in enumerate(lst):
                    if e is entry:
                        del lst[i]
                        break

        return Disposable(teardown)

    def emit(self, ev: Event) -> None:
        for sink, _throttle in list(self._subs.get(type(ev), ())):
            sink(ev)

    def _drain(self) -> None:
        """Flush all coalesced throttle payloads now — deterministic delivery
        for tests; in a running app the QTimer does this."""
        for subs in self._subs.values():
            for _sink, throttle in subs:
                if throttle is not None:
                    throttle.flush()

    def dispose(self) -> None:
        self._subs.clear()
