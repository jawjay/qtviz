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
    """Portable interaction state for **one surface** — preserved across
    rebuilds and backend switches (dev-plan [D2]). Each backend maps it to/from
    native ranges. `y2_range` is the twin axis ([D88]); `None` when the surface
    has none. A whole render's state is a `LayoutState` of these."""

    x_range: tuple[float, float] | None = None
    y_range: tuple[float, float] | None = None
    selection: tuple[int, ...] | None = None
    y2_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class LayoutState:
    """Portable interaction state for a whole render ([D150]): ordered
    `(pane label, ViewState)` pairs, one per surface. Restore matches **by
    label** — same label = same role, so state survives backend switches and
    root swaps; labels the new render doesn't have drop silently (a changed
    dashboard shape is not an error). Default pane labels are index strings
    (`"0"`, `"1"`, …), so unlabeled layouts degrade to positional matching.

    For the single-surface case (`x_range` & co.) the first pane's fields pass
    through, so `handle.capture_state().x_range` keeps reading naturally."""

    panes: tuple[tuple[str, ViewState], ...] = ()

    def get(self, label: str) -> ViewState | None:
        """The named pane's state, or `None`."""
        for lb, vs in self.panes:
            if lb == label:
                return vs
        return None

    @property
    def first(self) -> ViewState:
        """The first pane's state — the whole state of a single-surface render."""
        return self.panes[0][1] if self.panes else ViewState()

    # single-surface conveniences: the first pane's fields
    @property
    def x_range(self) -> tuple[float, float] | None:
        return self.first.x_range

    @property
    def y_range(self) -> tuple[float, float] | None:
        return self.first.y_range

    @property
    def y2_range(self) -> tuple[float, float] | None:
        return self.first.y2_range

    @property
    def selection(self) -> tuple[int, ...] | None:
        return self.first.selection


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


class PaneHandle:
    """One surface of a live render — the "Axes of qtviz" ([D147]). A thin
    facade over the *current* render, scoped strictly to **interaction-side**
    concerns: view ranges, programmatic brush, the native escape hatch.
    Describe-side config (title, scale, …) never flows through here — that is
    `.opts()` on the node; one-way data flow keeps rebuilds reasoned about.

    Facades are built fresh by `RenderHandle.panes()` on every call and go
    stale with the render they wrap — fetch fresh, never cache across a
    rebuild. All widget-touching methods are GUI-thread-only. The base class
    is an inert single pane, so any single-surface backend that predates the
    protocol is compliant with zero changes ([D125])."""

    def __init__(self, label: str) -> None:
        self.label = label  # plain attr: the composite host relabels flattened panes
        self._owner: RenderHandle | None = None  # set by RenderHandle.panes()

    @property
    def alive(self) -> bool:
        """Whether the render this pane wraps is still the live one. A pane
        kept across a rebuild/backend switch goes dead — its widgets are
        Qt-disposed — and every state-touching call raises `DisposedError`."""
        return self._owner is None or self._owner.widget is not None

    def _assert_alive(self) -> None:
        if not self.alive:
            from ..errors import DisposedError  # noqa: PLC0415

            raise DisposedError(
                f"pane {self.label!r} belongs to a disposed render — fetch a "
                f"fresh handle from the current one (view.pane(...))")

    def capture(self) -> ViewState:
        """This surface's current state, data space (R1)."""
        return ViewState()

    def restore(self, state: ViewState) -> None:
        """Apply `state` — `None` fields leave the current range untouched."""

    def set_range(self, *, x: tuple[float, float] | None = None,
                  y: tuple[float, float] | None = None,
                  y2: tuple[float, float] | None = None) -> None:
        """Programmatic pan/zoom sugar — data-space `(lo, hi)` per axis; omitted
        axes keep their current range. The same interaction-state class of
        change as a user drag, so events/rasters react identically."""
        self.restore(ViewState(x_range=x, y_range=y, y2_range=y2))

    def autorange(self) -> None:
        """Reset this surface to fit its data (the double-click/home verb)."""
        self._unsupported("autorange")

    def select(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Programmatic brush: emits the same per-element `SelectEvent`s a
        Shift-drag over `(x0, y0)–(x1, y1)` (data space) would."""
        self._unsupported("select")

    @property
    def native(self) -> Any:
        """The live backend surface primitive — a pg `PlotItem`, an mpl `Axes`,
        the webengine host ([D53]). Non-portable by design; `None` if unknown."""
        return None

    @property
    def elements(self) -> tuple[str, ...]:
        """Ids of the elements rendered on this surface (feed `View.on(source=…)`)."""
        return ()

    def _unsupported(self, verb: str) -> None:
        import warnings  # noqa: PLC0415

        from ..errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(f"pane {self.label!r}: {verb} is not supported by this "
                      f"backend and was ignored.", QtvizWarning, stacklevel=3)


class RenderHandle:
    """Owns a rendered widget tree — the bridge from immutable Elements to the
    mutable Qt world. Backends subclass to wire update/dispose/export/state.
    State is pane-based ([D150]): backends implement `panes()`; the base class
    derives whole-render capture/restore from it, written once here."""

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

    def toolbar(self) -> Any | None:
        """A backend-native toolbar QWidget for this render, or `None` when the
        backend's interaction is already native ([D95]). The View adds it above
        the canvas when constructed with `toolbar=True`."""
        return None

    def update(self, new_root) -> None:
        raise NotImplementedError

    def set_element_data(self, element_id: str, arrays: dict) -> bool:
        """Write new role-keyed arrays into the element's live primitive without a
        rebuild ([D77] — the incremental path behind `streaming=True`). Returns
        `False` when this backend/item can't (the caller falls back to
        `update()` or a rebuild — degradation is explicit, never silent)."""
        return False

    def release(self) -> None:
        """Dispose non-widget resources (bus throttles, raster controllers,
        selector hooks) when Qt is already tearing the widget tree down —
        View destruction. Re-parenting children mid-destruction is undefined
        behavior, so the widget references are dropped, not touched."""
        self.widget = None
        self.dispose()

    def dispose(self) -> None:
        import contextlib  # noqa: PLC0415

        self.event_bus.dispose()
        w = self.widget
        if w is not None:
            with contextlib.suppress(RuntimeError):  # C++ half may already be gone
                w.setParent(None)
                w.deleteLater()
        self.widget = None

    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        # [D125]: the widened signature every backend already implements,
        # formalized on the base instead of drifting per subclass.
        raise NotImplementedError

    def panes(self) -> tuple[PaneHandle, ...]:
        """One `PaneHandle` per surface, in layout child order (nested layouts
        flatten depth-first). Facades are built fresh per call and owned by
        this handle (dispose ⇒ they go dead). Backends implement `_panes()`;
        the base builds a single inert pane labeled `"0"` — a single-surface
        backend that overrides `capture_state`/`restore_state` wholesale (the
        pre-[D150] contract) still round-trips its own state."""
        ps = self._panes()
        for p in ps:
            p._owner = self
        return ps

    def _panes(self) -> tuple[PaneHandle, ...]:
        return (PaneHandle("0"),)

    def pane(self, key: str | int | None = None) -> PaneHandle:
        """A pane by label, by index, or — `key=None` — the only pane."""
        ps = self.panes()
        if key is None:
            if len(ps) != 1:
                from ..errors import ValidationError  # noqa: PLC0415

                raise ValidationError(
                    f"pane() needs a label or index when the render has "
                    f"{len(ps)} panes: {[p.label for p in ps]}")
            return ps[0]
        if isinstance(key, int):
            return ps[key]
        for p in ps:
            if p.label == key:
                return p
        raise KeyError(f"no pane labeled {key!r}; panes: {[p.label for p in ps]}")

    def capture_state(self) -> LayoutState:
        """Every pane's state, data space, keyed by pane label ([D150])."""
        return LayoutState(tuple((p.label, p.capture()) for p in self.panes()))

    def restore_state(self, state: LayoutState | ViewState) -> None:
        """Label-matched restore; unknown labels drop silently ([D150]). A bare
        `ViewState` is the single-surface shorthand: it applies to the first
        pane."""
        ps = self.panes()
        if isinstance(state, ViewState):
            if ps:
                ps[0].restore(state)
            return
        by_label = {p.label: p for p in ps}
        for label, vs in state.panes:
            target = by_label.get(label)
            if target is not None:
                target.restore(vs)


@runtime_checkable
class Backend(Protocol):
    """[D125] formalizes the de-facto surface: `honored_options` (the [D51]
    honor-or-warn source) and `requires_display` (webengine's live-compositor
    need) were required by core/tests but absent from the protocol. From
    wave 2, backends additionally carry `mark_drawers` (the [D122] mark
    adapters); it joins the protocol when it exists."""

    name: str
    capabilities: Capabilities
    renderers: RendererRegistry
    requires_display: bool

    def supports(self, element_type: type) -> bool: ...

    def honored_options(self, element_type: type) -> frozenset[str]: ...

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

    def __init__(self, widget: Any, child_handles: list[RenderHandle], *,
                 pane_labels: tuple[str, ...] | None = None) -> None:
        super().__init__(widget, _MergedBus([h.event_bus for h in child_handles]), "composite")
        self._children = child_handles
        self._pane_labels = pane_labels  # [D145]: flat labels from the Layout

    @property
    def children(self) -> list[RenderHandle]:
        return self._children

    def panes(self) -> tuple[PaneHandle, ...]:
        """The children's panes, flattened depth-first in child order and
        relabeled with the Layout's flat labels ([D145]; flat indices when the
        host gave none) — so a composite's state capture/restore ([D150])
        covers every pane exactly like a single-backend grid. Relabeling
        mutates only the fresh facades built by this call."""
        flat: list[PaneHandle] = []
        for h in self._children:
            flat.extend(h.panes())
        labels = self._pane_labels
        if labels is None or len(labels) != len(flat):
            labels = tuple(str(i) for i in range(len(flat)))
        for p, lb in zip(flat, labels, strict=True):
            p.label = lb
        return tuple(flat)

    def native(self, element_id: str) -> Any:
        """Fan out to the per-pane child handles (ids are unique; first hit wins)."""
        for h in self._children:
            item = h.native(element_id)
            if item is not None:
                return item
        return None

    def release(self) -> None:
        for h in self._children:
            h.widget = None
        super().release()

    def dispose(self) -> None:
        import contextlib  # noqa: PLC0415

        for h in self._children:
            h.dispose()
        w = self.widget
        if w is not None:
            with contextlib.suppress(RuntimeError):
                w.setParent(None)
                w.deleteLater()
        self.widget = None

    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        """One raster of the whole layout ([D72]): the Qt container — every pane
        plus chrome — grabbed via `QWidget.grab()`. png only: a single *vector*
        surface across backends is intrinsic to the no-unified-scene design and
        stays a non-goal ([D58]/R6); per-pane vector export remains available
        through `handle.children[i].export(...)`. Note a webengine pane needs a
        live compositor — offscreen it grabs blank."""
        if dpi is not None or transparent:  # honor-or-warn ([D51]/[D72])
            import warnings  # noqa: PLC0415

            from ..errors import QtvizWarning  # noqa: PLC0415

            warnings.warn("composite export: 'dpi'/'transparent' are not honored "
                          "(one QWidget.grab() raster at widget pixel size) and were "
                          "ignored; export panes individually for control.",
                          QtvizWarning, stacklevel=2)
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
