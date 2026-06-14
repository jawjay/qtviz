"""Private helper for linked-event coordination between PlotViews.

Used by the layout helpers (`PlotGrid`, `PlotTabs`, `PlotSplitter`) to wire
a source view's `received` signal to a handler called per-target. Each
helper owns its own list of `_Link`s and disconnects them when a referenced
view is removed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from qtviz.backends.webengine.backend import PlotBackend
    from qtviz.backends.webengine.view import PlotView


log = logging.getLogger("qtwebplot.linking")


class _Link:
    """One linked-event subscription.

    Listens to `source_view.received(name, payload)`; when `name` matches
    `event_name`, invokes `handler(target_backend, payload)` for every
    target view that still has a backend attached.
    """

    def __init__(
        self,
        source_view: "PlotView",
        event_name: str,
        target_views: list["PlotView"],
        handler: Callable[["PlotBackend", Any], None],
    ) -> None:
        self.source_view = source_view
        self.event_name = event_name
        self.target_views = list(target_views)
        self.handler = handler
        self._connected = True
        source_view.received.connect(self._on_received)

    def _on_received(self, name: str, payload: Any) -> None:
        if name != self.event_name:
            return
        for target in self.target_views:
            backend = target.backend
            if backend is None:
                continue
            try:
                self.handler(backend, payload)
            except Exception:
                log.exception(
                    "link handler raised for event=%r target=%r",
                    name,
                    type(backend).__name__,
                )

    def disconnect(self) -> None:
        if not self._connected:
            return
        try:
            self.source_view.received.disconnect(self._on_received)
        except (RuntimeError, TypeError):
            pass
        self._connected = False

    def references(self, view: "PlotView") -> bool:
        return view is self.source_view or view in self.target_views


def resolve_view(views: list["PlotView"], ref: "int | PlotView") -> "PlotView":
    """Index → view, or pass through a PlotView."""
    if isinstance(ref, int):
        if ref < 0 or ref >= len(views):
            raise IndexError(f"view index {ref} out of range [0, {len(views)})")
        return views[ref]
    return ref
