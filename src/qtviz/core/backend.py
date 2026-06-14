"""The backend plug-in contract (spec §2.4–§2.8).

Everything a backend must provide, and the handle it returns. Core depends on
this protocol; never on a concrete backend.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .capabilities import Capabilities
from .disposable import Disposable
from .element import Element
from .event import EventBus
from .theme import Theme

ElementRenderer = Callable[[Element, "RenderContext"], Any]
BackendPrimitive = Any


@dataclass(frozen=True)
class ViewState:
    """Portable interaction state — preserved across rebuilds and backend
    switches (dev-plan [D2]). Each backend maps it to/from native ranges."""

    x_range: tuple[float, float] | None = None
    y_range: tuple[float, float] | None = None
    selection: tuple[int, ...] | None = None


@dataclass
class RenderContext:
    theme: Theme
    parent: Any                  # the surface to attach to (QWidget)
    event_bus: EventBus
    backend: Backend
    parent_axes: Any = None      # ViewBox / Axes for overlay children


class RendererRegistry:
    """A backend's Element-type → renderer map."""

    def __init__(self) -> None:
        self._fns: dict[type, ElementRenderer] = {}

    def register(self, element_type: type, fn: ElementRenderer) -> None:
        self._fns[element_type] = fn

    def get(self, element_type: type) -> ElementRenderer | None:
        return self._fns.get(element_type)

    def types(self) -> set[type]:
        return set(self._fns)


class RenderHandle:
    """Owns a rendered widget tree — the bridge from immutable Elements to the
    mutable Qt world. Backends subclass to wire update/dispose/export/state."""

    def __init__(self, widget: Any, event_bus: EventBus, backend_name: str) -> None:
        self.widget = widget
        self.event_bus = event_bus
        self.backend_name = backend_name

    def update(self, new_root) -> None:
        raise NotImplementedError

    def dispose(self) -> None:
        self.event_bus.dispose()
        w = self.widget
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        self.widget = None

    def export(self, fmt: str, path) -> Path:
        raise NotImplementedError

    def capture_state(self) -> ViewState:
        return ViewState()

    def restore_state(self, state: ViewState) -> None:
        pass


@runtime_checkable
class Backend(Protocol):
    name: str
    capabilities: Capabilities
    renderers: RendererRegistry

    def supports(self, element_type: type) -> bool: ...

    def render(self, node, *, theme: Theme, parent: Any = None) -> RenderHandle: ...

    def can_host(self, kind: str) -> bool: ...


class _MergedBus:
    """The event bus of a CompositeRenderHandle. A subscription fans out to
    every child bus, so `View.on(...)` sees one stream no matter how many
    panes/backends sit underneath (spec §2.8)."""

    def __init__(self, child_buses) -> None:
        self._buses = list(child_buses)

    def subscribe(self, event_type, cb, *, throttle_ms=None) -> Disposable:
        disposables = [b.subscribe(event_type, cb, throttle_ms=throttle_ms) for b in self._buses]
        return Disposable(lambda: [d.dispose() for d in disposables])

    def emit(self, ev) -> None:
        for b in self._buses:
            b.emit(ev)

    def _drain(self) -> None:
        for b in self._buses:
            b._drain()

    def dispose(self) -> None:
        for b in self._buses:
            b.dispose()


class CompositeRenderHandle(RenderHandle):
    """A Layout whose panes span backends (or a splitter/tabs/dock container):
    the widget is a Qt container built by the LayoutHost (§3.7), and the bus
    is merged over the per-pane child handles. View holds exactly one root
    handle — a backend handle or one of these."""

    def __init__(self, widget: Any, child_handles: list[RenderHandle]) -> None:
        super().__init__(widget, _MergedBus([h.event_bus for h in child_handles]), "composite")
        self._children = child_handles

    @property
    def children(self) -> list[RenderHandle]:
        return self._children

    def dispose(self) -> None:
        for h in self._children:
            h.dispose()
        w = self.widget
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        self.widget = None

    def export(self, fmt: str, path) -> Path:
        raise NotImplementedError(
            "a composite (mixed-backend) view has no single surface to export; "
            "export each pane via its own handle (handle.children[i].export(...))"
        )
