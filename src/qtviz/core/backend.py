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
