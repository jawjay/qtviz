"""`InsetIndicator` — the live inset zoom indicator ([D154] I4b).

The `_LinkController` shape (`core/_host.py`), but per backend handle: one
subscription on the handle's `EventBus`, filtered to the inset's pane
label; every `RangeEvent` from inside the inset calls the backend-supplied
`move(x0, y0, x1, y1)` (data space) to reposition the parent-side
rectangle natively. It lives with the raster controllers on the parent
surface and disposes with them.
"""

from __future__ import annotations

from collections.abc import Callable


class InsetIndicator:
    """Keeps the parent-side zoom rectangle on the inset's visible window.

    `window` seeds the last-known `((x0, x1), (y0, y1))` — either the
    child's declared lims or the rendered (autoranged) window — so a
    single-axis `RangeEvent` still yields a full rectangle."""

    def __init__(self, bus, pane_label: str, window, move: Callable) -> None:
        from .event import RangeEvent  # noqa: PLC0415

        self._label = pane_label
        self._move = move
        self._x, self._y = tuple(window[0]), tuple(window[1])
        self._sub = bus.subscribe(RangeEvent, self._on_range)

    def _on_range(self, ev) -> None:
        # A throttled trailing delivery can land after disposal — the sub is
        # gone by then; anything arriving here is live.
        if ev.pane != self._label:
            return
        if ev.x is not None:
            self._x = (float(ev.x[0]), float(ev.x[1]))
        if ev.y is not None:
            self._y = (float(ev.y[0]), float(ev.y[1]))
        x0, x1 = sorted(self._x)
        y0, y1 = sorted(self._y)
        if x0 < x1 and y0 < y1:  # degenerate windows draw nothing new
            self._move(x0, y0, x1, y1)

    def dispose(self) -> None:
        self._sub.dispose()
