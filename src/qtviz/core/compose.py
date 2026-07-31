"""Composition + backend negotiation (spec §2.3, §3.2, §3.3).

`Overlay` (same axes, layered, single backend) and `Layout` (side-by-side,
mixed backends allowed) plus the `*` / `+` operators. Negotiation is pure — it
reads only the registry's `supports()` + priority, never builds a widget — so
it is unit-testable headless against stub backends.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Literal, Union

from ..errors import IncompatibleOverlayError, NoBackendForError, UnsupportedElementError
from ._immutable import Immutable
from .element import Element
from .options import LayoutOptions, OverlayOptions

Node = Union[Element, "Overlay", "Layout"]


class Overlay(Immutable):
    """Same axes, layered. Built by `*`. Single-surface → single backend."""

    def __init__(self, children: Sequence[Node], *,
                 options: OverlayOptions | None = None,
                 backend_hint: str | None = None) -> None:
        self.children = tuple(children)
        self.options = options or OverlayOptions()
        self.backend_hint = backend_hint
        if not self.children:
            raise ValueError("Overlay requires at least one child")
        self._freeze()

    def __mul__(self, other: Node) -> Overlay:
        return Overlay(self.children + (other,), options=self.options,
                       backend_hint=self.backend_hint)

    def __add__(self, other: Node) -> Layout:
        return Layout((self, other))

    def over(self, other: Node) -> Overlay:
        return self.__mul__(other)


class Layout(Immutable):
    """Side-by-side / grid / splitter / tabs / dock. Built by `+`. Children
    may use different backends."""

    def __init__(self, children: Sequence[Node], *,
                 kind: Literal["grid", "splitter", "tabs", "dock"] = "grid",
                 options: LayoutOptions | None = None,
                 backend_hint: str | None = None) -> None:
        self.children = tuple(children)
        self.kind = kind
        self.options = options or LayoutOptions()
        self.backend_hint = backend_hint
        if not self.children:
            raise ValueError("Layout requires at least one child")
        self._freeze()

    def __add__(self, other: Node) -> Layout:
        return Layout(self.children + (other,), kind=self.kind, options=self.options,
                      backend_hint=self.backend_hint)

    def __mul__(self, other: Node) -> Overlay:
        return Overlay((self, other))

    @classmethod
    def grid(cls, children, **kw) -> Layout:
        return cls(children, kind="grid", **kw)

    @classmethod
    def tabs(cls, children, **kw) -> Layout:
        return cls(children, kind="tabs", **kw)

    @classmethod
    def splitter(cls, children, **kw) -> Layout:
        return cls(children, kind="splitter", **kw)


def surface_of(node: Node) -> OverlayOptions:
    """The shared-surface options for any renderable node (the axis-surface seam,
    Phase A). An `Overlay` carries its own `OverlayOptions`; a bare `Element` (or
    anything else a backend renders as one surface) gets defaults. This lets every
    backend apply title/axis-labels uniformly without special-casing bare elements.
    See `design/axis-surface-feasibility.md`."""
    return node.options if isinstance(node, Overlay) else OverlayOptions()


def resolve_scale(requested: str, available, *, axis: str, backend: str) -> str:
    """Effective axis scale: the requested scale if `backend` declares it in
    `Capabilities.scales`, else **linear** with a one-time `QtvizWarning` (the
    capability-gated warn-and-degrade contract, feasibility §2.3 / [D59]). Linear is
    always available, so a default surface never warns."""
    if requested in available:
        return requested
    if requested != "linear":
        import warnings  # noqa: PLC0415

        from ..errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(
            f"{backend}: {axis} scale={requested!r} not supported by this backend; "
            f"using 'linear'.",
            QtvizWarning,
            stacklevel=2,
        )
    return "linear"


def effective_scales(node: Node, surf: OverlayOptions, available, backend: str) -> tuple[str, str]:
    """The `(x_scale, y_scale)` a backend should actually render for one surface:
    each axis capability-gated by `resolve_scale`, then — if the surface holds any
    raster (`Image` / `Heatmap`, incl. a datashaded Scatter/Curve, which resolves to
    `Image`) — forced back to linear with a warning. A raster is never
    log-transformed ([D59] defer + gate; feasibility §10.4)."""
    x_scale = resolve_scale(surf.x.scale, available, axis="x", backend=backend)
    y_scale = resolve_scale(surf.y.scale, available, axis="y", backend=backend)
    if x_scale == y_scale == "linear":
        return (x_scale, y_scale)
    from ..elements import Contour, Heatmap, Image  # noqa: PLC0415 — avoid a core→elements cycle

    if any(isinstance(e, (Image, Heatmap, Contour)) for e in _elements_of(node)):
        import warnings  # noqa: PLC0415

        from ..errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(
            f"{backend}: a raster (Image/Heatmap or datashaded) surface doesn't "
            f"support non-linear axis scales yet; rendering linear.",
            QtvizWarning,
            stacklevel=2,
        )
        return ("linear", "linear")
    return (x_scale, y_scale)


def series_index_map(children) -> list[int]:
    """Per-child palette slot for one surface: data elements count 0, 1, 2, …;
    annotation/reference elements are chrome — they get slot 0 (unused; their
    default color is the theme foreground) and do NOT shift the series that
    follow. The single source of truth for default-color cycling and
    `legend_entry(index=…)`, shared by all three backends ([D70])."""
    from ..elements.annotations import ANNOTATION_TYPES  # noqa: PLC0415

    out: list[int] = []
    i = 0
    for el in children:
        if isinstance(el, ANNOTATION_TYPES):
            out.append(0)
        else:
            out.append(i)
            i += 1
    return out


def _elements_of(node: Node) -> Iterator[Element]:
    if isinstance(node, Element):
        yield node
    elif isinstance(node, (Overlay, Layout)):
        for child in node.children:
            yield from _elements_of(child)


def _data_size(el: Element) -> int | None:
    try:
        return el.data.size()
    except Exception:
        return None


# ── negotiation ──────────────────────────────────────────────────────────────
def negotiate(node: Node, view_backend: str | None, *, ancestor_hint: str | None = None) -> str:
    """Resolve the backend name for `node` from its hint, ancestors, the view choice,
    and the global default; raises if an Overlay's children disagree or an Element is
    unsupported. `"auto"` defers to `auto_negotiate`."""
    from .. import backends

    chosen = (node.backend_hint or ancestor_hint or view_backend
              or backends.global_default() or "auto")
    if chosen == "auto":
        return auto_negotiate(node, ancestor_hint=ancestor_hint)

    if isinstance(node, Overlay):
        for child in node.children:
            child_chosen = negotiate(child, view_backend, ancestor_hint=chosen)
            if child_chosen != chosen:
                raise IncompatibleOverlayError(
                    f"Overlay requires one backend but children resolve to "
                    f"{chosen!r} and {child_chosen!r}"
                )
        return chosen

    if isinstance(node, Layout):
        for child in node.children:
            negotiate(child, view_backend, ancestor_hint=chosen)  # panes may differ
        return chosen

    # Element
    backend = backends.get(chosen)
    if not backend.supports(type(node)):
        supported = [b.name for b in backends.registered() if b.supports(type(node))]
        raise UnsupportedElementError(
            f"{type(node).__name__} not supported on {chosen!r}; "
            f"supported on: {supported}"
        )
    return chosen


def auto_negotiate(node: Node, *, ancestor_hint: str | None = None) -> str:
    """Pick a backend for `node` by capability + data size when no explicit choice is
    given — the engine behind `backend="auto"`."""
    from .. import backends

    if isinstance(node, Overlay):
        elems = list(_elements_of(node))
        # intersect-first: a single backend must support *every* child (D4).
        common = [
            b for b in backends.registered()
            if all(b.supports(type(e)) for e in elems)
        ]
        if not common:
            raise IncompatibleOverlayError(
                "no single backend supports all overlay children: "
                f"{sorted({type(e).__name__ for e in elems})}"
            )
        return _pick(common, max((_data_size(e) or 0) for e in elems))

    if isinstance(node, Layout):
        for child in node.children:
            auto_negotiate(child)
        return "auto"

    candidates = [b for b in backends.registered() if b.supports(type(node))]
    if not candidates:
        raise NoBackendForError(f"no registered backend supports {type(node).__name__}")
    return _pick(candidates, _data_size(node))


def _pick(candidates, n: int | None) -> str:
    from .. import backends

    if n is not None and n > 1_000_000:
        return max(candidates, key=lambda b: b.capabilities.max_recommended_points).name
    return max(candidates, key=lambda b: -backends.priority_index(b.name)).name
