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
    switches (dev-plan [D2]). Each backend maps it to/from native ranges.
    `y2_range` is the twin axis ([D88]); `None` when the surface has none."""

    x_range: tuple[float, float] | None = None
    y_range: tuple[float, float] | None = None
    selection: tuple[int, ...] | None = None
    y2_range: tuple[float, float] | None = None


@dataclass
class RenderContext:
    theme: Theme
    parent: Any                  # the surface to attach to (QWidget)
    event_bus: EventBus
    backend: Backend
    parent_axes: Any = None      # ViewBox / Axes for overlay children
    # Effective (capability-gated) axis scales for this surface ([D59]). Renderers
    # that must pre-transform data (pyqtgraph) read these; others may ignore them.
    x_scale: str = "linear"
    y_scale: str = "linear"
    # Surface legend policy ([D60]): renderers that draw their own legends (a
    # `color_by` Scatter, a datashaded raster) consult these instead of drawing
    # unconditionally, so `OverlayOptions.legend=False` silences every path.
    show_legend: bool = True
    legend_position: str = "auto"
    # This element's palette slot on its surface (`series_index_map`): default
    # colors cycle by it, matching legend_entry(index=…) on every backend.
    series_index: int = 0


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

    def __init__(self, widget: Any, event_bus: Any, backend_name: str) -> None:
        self.widget = widget
        self.event_bus = event_bus
        self.backend_name = backend_name
        # element id → live backend primitive, populated at render (see native()).
        self._natives: dict[str, Any] = {}

    def native(self, element_id: str) -> Any:
        """The live backend primitive for an element — a pg `PlotItem`, an mpl
        `Artist`/`Axes`, or the webengine figure host — or `None` if unknown / not
        yet rendered. The post-0.1 escape valve ([D53]) for reaching backend-native
        power (ROIs, crosshairs, native signals) the typed event/element
        vocabularies don't expose.

        **Non-portable by design:** the returned type is backend-specific and code
        using it opts out of "swap the backend, same behavior." The live object is
        returned *through the handle*, never stored on the immutable Element, so the
        purity/value-hash invariant (§2.1) is untouched. The map rebuilds on
        `update()` / a backend switch, so this always reflects the current render."""
        return self._natives.get(element_id)

    def update(self, new_root) -> None:
        raise NotImplementedError

    def set_element_data(self, element_id: str, arrays: dict) -> bool:
        """Write new role-keyed arrays into the element's live primitive without a
        rebuild ([D77] — the incremental path behind `streaming=True`). Returns
        `False` when this backend/item can't (the caller falls back to
        `update()` or a rebuild — degradation is explicit, never silent)."""
        return False

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

        def dispose_all() -> None:
            for d in disposables:
                d.dispose()

        return Disposable(dispose_all)

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

    def native(self, element_id: str) -> Any:
        """Fan out to the per-pane child handles (ids are unique; first hit wins)."""
        for h in self._children:
            item = h.native(element_id)
            if item is not None:
                return item
        return None

    def dispose(self) -> None:
        for h in self._children:
            h.dispose()
        w = self.widget
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        self.widget = None

    def export(self, fmt: str, path) -> Path:
        """One raster of the whole layout ([D72]): the Qt container — every pane
        plus chrome — grabbed via `QWidget.grab()`. png only: a single *vector*
        surface across backends is intrinsic to the no-unified-scene design and
        stays a non-goal ([D58]/R6); per-pane vector export remains available
        through `handle.children[i].export(...)`. Note a webengine pane needs a
        live compositor — offscreen it grabs blank."""
        if fmt != "png":
            raise NotImplementedError(
                "a composite (mixed-backend) view exports png only (one raster of "
                "the whole container, [D72]); vector export is per-pane: "
                "handle.children[i].export(...)"
            )
        path = Path(path)
        w = self.widget
        if w.size().isEmpty():
            w.resize(800, 600)  # grab needs a non-empty widget
        w.grab().save(str(path), "PNG")
        return path
