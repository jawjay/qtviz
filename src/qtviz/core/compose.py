"""Composition + backend negotiation (spec §2.3, §3.2, §3.3).

`Overlay` (same axes, layered, single backend) and `Layout` (side-by-side,
mixed backends allowed) plus the `*` / `+` operators. Negotiation is pure — it
reads only the registry's `supports()` + priority, never builds a widget — so
it is unit-testable headless against stub backends.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Literal, Union

from ..errors import (
    IncompatibleOverlayError,
    NoBackendForError,
    UnsupportedElementError,
    ValidationError,
)
from ._immutable import Immutable
from .element import Element
from .options import UNSET, AxisSpec, LayoutOptions, OverlayOptions

Node = Union[Element, "Overlay", "Layout"]

Cell = tuple[int, int, int, int]  # (row, col, rowspan, colspan)


def parse_mosaic(spec: str) -> dict[str, Cell]:
    """Parse a `subplot_mosaic`-style string ([D108]) into per-label
    `(row, col, rowspan, colspan)` cells, ordered by first appearance.

    Rows are newline- (or `;`-) separated; each character is one grid cell;
    `.` (or a space) is a hole. Every label's cells must form one solid
    rectangle — anything else is ambiguous and raises `ValidationError`."""
    from ..errors import ValidationError  # noqa: PLC0415

    rows = [r for r in spec.replace(";", "\n").splitlines() if r.strip()]
    if not rows:
        raise ValidationError("mosaic spec is empty")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValidationError(
            f"mosaic rows must be equal length, got {[len(r) for r in rows]}")
    boxes: dict[str, list[int]] = {}          # label → [r0, c0, r1, c1]
    order: list[str] = []
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch in ". ":
                continue
            if ch not in boxes:
                boxes[ch] = [r, c, r, c]
                order.append(ch)
            else:
                b = boxes[ch]
                b[0], b[1] = min(b[0], r), min(b[1], c)
                b[2], b[3] = max(b[2], r), max(b[3], c)
    for label in order:  # solid-rectangle check: every cell in the bbox is `label`
        r0, c0, r1, c1 = boxes[label]
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if rows[r][c] != label:
                    raise ValidationError(
                        f"mosaic label {label!r} does not form a solid rectangle")
    return {label: (b[0], b[1], b[2] - b[0] + 1, b[3] - b[1] + 1)
            for label, b in ((lb, boxes[lb]) for lb in order)}


class Overlay(Immutable):
    """Same axes, layered. Built by `*`. Single-surface → single backend."""

    def __init__(self, children: Sequence[Node], *,
                 options: OverlayOptions | None = None,
                 backend_hint: str | None = None) -> None:
        self.children = tuple(children)
        self.options = options or OverlayOptions()
        self.backend_hint = backend_hint
        if not self.children:
            raise ValidationError("Overlay requires at least one child")
        self._freeze()

    def __mul__(self, other: Node) -> Overlay:
        return Overlay(self.children + (other,), options=self.options,
                       backend_hint=self.backend_hint)

    def __add__(self, other: Node) -> Layout:
        return Layout((self, other))

    def over(self, other: Node) -> Overlay:
        return self.__mul__(other)

    def opts(self, *, title=UNSET, x=UNSET, y=UNSET, y2=UNSET, aspect=UNSET,
             legend=UNSET, background=UNSET, grid=UNSET) -> Overlay:
        """[D133] field-wise options merge: only the fields you pass change
        (`UNSET` keeps; `None` clears where meaningful). For `x`/`y`/`y2` a
        bare string merges into the existing spec's `.label`; a full
        `AxisSpec` replaces it. Chains — later calls win per field."""
        cur = self.options
        def axis(new, old):
            if new is UNSET:
                return old
            if isinstance(new, str):
                base = old if isinstance(old, AxisSpec) else AxisSpec()
                return base.with_(label=new)
            return new
        merged = OverlayOptions(
            title=cur.title if title is UNSET else title,
            x=axis(x, cur.x), y=axis(y, cur.y), y2=axis(y2, cur.y2),
            aspect=cur.aspect if aspect is UNSET else aspect,
            legend=cur.legend if legend is UNSET else legend,
            background=cur.background if background is UNSET else background,
            grid=cur.grid if grid is UNSET else grid,
        )
        return Overlay(self.children, options=merged, backend_hint=self.backend_hint)

    def __repr__(self) -> str:
        shown = {k: v for k, v in self.options._fields().items()
                 if v != getattr(OverlayOptions(), k)}
        inner = ", ".join(f"{k}={v!r}" for k, v in shown.items())
        return (f"Overlay({len(self.children)} children"
                + (f", {inner}" if inner else "") + ")")


class Layout(Immutable):
    """Side-by-side / grid / splitter / tabs / dock. Built by `+`. Children
    may use different backends. A grid built by `Layout.mosaic` additionally
    carries per-child `cells` — `(row, col, rowspan, colspan)` — so panes can
    span ([D108])."""

    def __init__(self, children: Sequence[Node], *,
                 kind: Literal["grid", "splitter", "tabs", "dock"] = "grid",
                 options: LayoutOptions | None = None,
                 backend_hint: str | None = None,
                 cells: Sequence[Cell] | None = None) -> None:
        self.children = tuple(children)
        self.kind = kind
        self.options = options or LayoutOptions()
        self.backend_hint = backend_hint
        self.cells: tuple[Cell, ...] | None = (
            tuple((int(r), int(c), int(rs), int(cs)) for r, c, rs, cs in cells)
            if cells else None)
        if not self.children:
            raise ValidationError("Layout requires at least one child")
        if self.cells is not None and len(self.cells) != len(self.children):
            raise ValidationError(
                f"cells ({len(self.cells)}) must match children ({len(self.children)})")
        self._freeze()

    def __add__(self, other: Node) -> Layout:
        if self.cells is not None:  # a mosaic is a sealed shape — nest, don't append
            return Layout((self, other))
        return Layout(self.children + (other,), kind=self.kind, options=self.options,
                      backend_hint=self.backend_hint)

    def __mul__(self, other: Node) -> Overlay:
        return Overlay((self, other))

    def opts(self, *, title=UNSET, rows=UNSET, cols=UNSET, spacing=UNSET,
             link_x=UNSET, link_y=UNSET, tab_labels=UNSET,
             width_ratios=UNSET, height_ratios=UNSET) -> Layout:
        """[D133] field-wise merge of the layout options (`title` here is the
        container suptitle). Only passed fields change; chains."""
        cur = self.options
        merged = LayoutOptions(
            rows=cur.rows if rows is UNSET else rows,
            cols=cur.cols if cols is UNSET else cols,
            spacing=cur.spacing if spacing is UNSET else spacing,
            link_x=cur.link_x if link_x is UNSET else link_x,
            link_y=cur.link_y if link_y is UNSET else link_y,
            tab_labels=cur.tab_labels if tab_labels is UNSET else tab_labels,
            dock_areas=cur.dock_areas,
            title=cur.title if title is UNSET else title,
            width_ratios=cur.width_ratios if width_ratios is UNSET else width_ratios,
            height_ratios=cur.height_ratios if height_ratios is UNSET else height_ratios,
        )
        return Layout(self.children, kind=self.kind, options=merged,
                      backend_hint=self.backend_hint, cells=self.cells)

    def __repr__(self) -> str:
        shown = {k: v for k, v in self.options._fields().items()
                 if v != getattr(LayoutOptions(), k)}
        inner = ", ".join(f"{k}={v!r}" for k, v in shown.items())
        return (f"Layout({len(self.children)} children, kind={self.kind!r}"
                + (f", {inner}" if inner else "") + ")")

    @classmethod
    def grid(cls, children, **kw) -> Layout:
        return cls(children, kind="grid", **kw)

    @classmethod
    def mosaic(cls, spec: str, *, options: LayoutOptions | None = None,
               backend_hint: str | None = None, **panes: Node) -> Layout:
        """A grid from an ASCII plan ([D108], the `subplot_mosaic` precedent):

            Layout.mosaic("AAB\\nCCB", A=curve, B=sidebar, C=table)

        Each distinct character is one pane (spanning its rectangle); `.` is a
        hole. Every label in the spec must be passed as a keyword, and vice
        versa."""
        from ..errors import ValidationError  # noqa: PLC0415

        cells_by_label = parse_mosaic(spec)
        missing = [lb for lb in cells_by_label if lb not in panes]
        extra = [k for k in panes if k not in cells_by_label]
        if missing or extra:
            raise ValidationError(
                f"mosaic panes must match the spec labels exactly; "
                f"missing={missing}, unknown={extra}")
        return cls([panes[lb] for lb in cells_by_label], kind="grid",
                   options=options, backend_hint=backend_hint,
                   cells=list(cells_by_label.values()))

    @classmethod
    def tabs(cls, children, **kw) -> Layout:
        return cls(children, kind="tabs", **kw)

    @classmethod
    def splitter(cls, children, **kw) -> Layout:
        return cls(children, kind="splitter", **kw)


def grid_geometry(layout: Layout) -> tuple[list[Cell], int, int]:
    """`(cells, nrows, ncols)` for a grid Layout — the one place grid shape is
    decided, shared by every consumer (mpl figure, pg layout, Qt host) so a
    given Layout has the same shape everywhere ([D108]). Mosaic cells pass
    through; otherwise children flow row-major into `cols` columns (or into
    `ceil(n / rows)` columns when only `rows` is set)."""
    from math import ceil  # noqa: PLC0415

    if layout.cells is not None:
        cells = list(layout.cells)
        nrows = max(r + rs for r, _, rs, _ in cells)
        ncols = max(c + cs for _, c, _, cs in cells)
        return cells, nrows, ncols
    n = len(layout.children)
    opts = layout.options
    ncols = opts.cols or (ceil(n / opts.rows) if opts.rows else n)
    nrows = ceil(n / ncols)
    return [(i // ncols, i % ncols, 1, 1) for i in range(n)], nrows, ncols


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


def _any_datetime(node: Node, role: str) -> bool:
    """Any data element whose resolved `role` channel is datetime64 ([D94]).
    Best-effort: unresolved refs (or elements without the role) contribute
    nothing — promotion happens at render, where the node is resolved."""
    for el in _elements_of(node):
        try:
            if el.data.series(role).dtype.kind == "M":
                return True
        except Exception:  # noqa: BLE001,S112 — no such role / unresolved ref
            continue
    return False


def effective_scales(node: Node, surf: OverlayOptions, available, backend: str) -> tuple[str, str]:
    """The `(x_scale, y_scale)` a backend should actually render for one surface:
    each axis capability-gated by `resolve_scale`; a linear axis whose data is
    datetime64 promotes to `"time"` ([D94] — calendar dressing only; the data
    space stays linear epoch seconds); then — if the surface holds any raster
    (`Image` / `Heatmap` / `Contour`, incl. a datashaded Scatter/Curve, which
    resolves to `Image`) — a *transforming* scale (log/symlog) is forced back to
    linear with a warning. A raster is never log-transformed ([D59] defer +
    gate; feasibility §10.4); `time` doesn't transform, so it passes."""
    x_scale = resolve_scale(surf.x.scale, available, axis="x", backend=backend)
    y_scale = resolve_scale(surf.y.scale, available, axis="y", backend=backend)
    if x_scale == "linear" and _any_datetime(node, "x"):
        x_scale = resolve_scale("time", available, axis="x", backend=backend)
    if y_scale == "linear" and _any_datetime(node, "y"):
        y_scale = resolve_scale("time", available, axis="y", backend=backend)
    if {x_scale, y_scale} <= {"linear", "time"}:
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
