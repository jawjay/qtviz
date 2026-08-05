"""Composition + backend negotiation (spec §2.3, §3.2, §3.3).

`Overlay` (same axes, layered, single backend) and `Layout` (side-by-side,
mixed backends allowed) plus the `*` / `+` operators. Negotiation is pure — it
reads only the registry's `supports()` + priority, never builds a widget — so
it is unit-testable headless against stub backends.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Literal, Union

from ..errors import (
    IncompatibleOverlayError,
    NoBackendForError,
    UnsupportedElementError,
    ValidationError,
)
from ._immutable import Immutable
from .color import ColorSpec
from .element import Element
from .options import UNSET, AxisSpec, LayoutOptions, OverlayOptions, _Unset

Node = Union[Element, "Overlay", "Layout"]

Cell = tuple[int, int, int, int]  # (row, col, rowspan, colspan)


MosaicSpec = str | Sequence[Sequence["str | None"]]


def parse_mosaic(spec: MosaicSpec) -> dict[str, Cell]:
    """Parse a `subplot_mosaic`-style plan ([D108]/[D145]) into per-label
    `(row, col, rowspan, colspan)` cells, ordered by first appearance.

    Two spellings, the `subplot_mosaic` precedents: a **string** — rows
    newline- (or `;`-) separated, each character one grid cell, `.` (or a
    space) a hole — or a **list of rows of labels**, where labels are
    arbitrary strings and `None` (or `"."`) is a hole:

        parse_mosaic("AAB;CCB")
        parse_mosaic([["price", "book"], ["volume", "book"]])

    Every label's cells must form one solid rectangle — anything else is
    ambiguous and raises `ValidationError`."""
    from ..errors import ValidationError  # noqa: PLC0415

    if isinstance(spec, str):
        lines = [r for r in spec.replace(";", "\n").splitlines() if r.strip()]
        rows: list[list[str | None]] = [
            [None if ch in ". " else ch for ch in line] for line in lines]
    else:
        rows = [[None if tok in (None, ".") else str(tok) for tok in line]
                for line in spec]
    if not rows:
        raise ValidationError("mosaic spec is empty")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValidationError(
            f"mosaic rows must be equal length, got {[len(r) for r in rows]}")
    boxes: dict[str, list[int]] = {}          # label → [r0, c0, r1, c1]
    order: list[str] = []
    for r, line in enumerate(rows):
        for c, label in enumerate(line):
            if label is None:
                continue
            if label not in boxes:
                boxes[label] = [r, c, r, c]
                order.append(label)
            else:
                b = boxes[label]
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


def _validate_cells(cells: Sequence[Cell], where: str) -> None:
    """Explicit-`cells` validation ([D148]) — the same guarantees the mosaic
    parser gives: positive spans, no overlapping panes."""
    from ..errors import ValidationError  # noqa: PLC0415

    occupied: dict[tuple[int, int], int] = {}
    for i, (r, c, rs, cs) in enumerate(cells):
        if r < 0 or c < 0 or rs < 1 or cs < 1:
            raise ValidationError(
                f"{where}: cell {i} {(r, c, rs, cs)!r} must have row/col >= 0 "
                f"and spans >= 1")
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                if (rr, cc) in occupied:
                    raise ValidationError(
                        f"{where}: cells {occupied[(rr, cc)]} and {i} overlap "
                        f"at (row {rr}, col {cc})")
                occupied[(rr, cc)] = i


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

    def opts(self, *,
             title: str | None | _Unset = UNSET,
             x: AxisSpec | str | None | _Unset = UNSET,
             y: AxisSpec | str | None | _Unset = UNSET,
             y2: AxisSpec | str | None | _Unset = UNSET,
             aspect: float | None | _Unset = UNSET,
             legend: bool | str | _Unset = UNSET,
             background: ColorSpec | None | _Unset = UNSET,
             grid: bool | _Unset = UNSET) -> Overlay:
        """Field-wise options merge: only the fields you pass change
        (`UNSET` keeps; `None` clears where meaningful). For `x`/`y`/`y2` a
        bare string merges into the existing spec's `.label`; a full
        `AxisSpec` replaces it. Chains — later calls win per field."""
        cur = self.options
        def axis(new, old):
            if isinstance(new, _Unset):
                return old
            if isinstance(new, str):
                base = old if isinstance(old, AxisSpec) else AxisSpec()
                return base.with_(label=new)
            return new
        merged = OverlayOptions(
            title=cur.title if isinstance(title, _Unset) else title,
            x=axis(x, cur.x), y=axis(y, cur.y), y2=axis(y2, cur.y2),
            aspect=cur.aspect if isinstance(aspect, _Unset) else aspect,
            legend=cur.legend if isinstance(legend, _Unset) else legend,
            background=cur.background if isinstance(background, _Unset) else background,
            grid=cur.grid if isinstance(grid, _Unset) else grid,
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
    span.

    Children may be **named** ([D145]): pass a mapping (`Layout.grid({"price":
    p, "volume": v})`), a mosaic (labels retained), or explicit `labels=`.
    Labels name the direct children — `layout["price"]` looks one up,
    `layout.with_pane("price", node)` swaps one immutably — and become the
    pane labels downstream (state capture/restore keys, `view.pane(...)`,
    event scoping). Unlabeled panes get their flat index as a string."""

    def __init__(self, children: Sequence[Node] | Mapping[str, Node], *,
                 kind: Literal["grid", "splitter", "tabs", "dock"] = "grid",
                 options: LayoutOptions | None = None,
                 backend_hint: str | None = None,
                 cells: Sequence[Cell] | None = None,
                 labels: Sequence[str] | None = None) -> None:
        if isinstance(children, Mapping):
            if labels is not None:
                raise ValidationError(
                    "pass labels either as mapping keys or as labels=, not both")
            labels = tuple(str(k) for k in children)
            children = tuple(children.values())
        self.children = tuple(children)
        self.kind = kind
        self.options = options or LayoutOptions()
        self.backend_hint = backend_hint
        self.cells: tuple[Cell, ...] | None = (
            tuple((int(r), int(c), int(rs), int(cs)) for r, c, rs, cs in cells)
            if cells else None)
        self.labels: tuple[str, ...] | None = (
            tuple(str(lb) for lb in labels) if labels is not None else None)
        if not self.children:
            raise ValidationError("Layout requires at least one child")
        if self.cells is not None and len(self.cells) != len(self.children):
            raise ValidationError(
                f"cells ({len(self.cells)}) must match children ({len(self.children)})")
        if self.kind != "grid":  # [D146]: col/row sharing is grid geometry
            for name in ("link_x", "link_y"):
                if getattr(self.options, name) in ("col", "row"):
                    raise ValidationError(
                        f"{name}={getattr(self.options, name)!r} needs a grid "
                        f"layout, got kind={self.kind!r} (True links all panes)")
        if self.cells is not None:
            _validate_cells(self.cells, where="Layout cells")
        if self.labels is not None:
            if len(self.labels) != len(self.children):
                raise ValidationError(
                    f"labels ({len(self.labels)}) must match children "
                    f"({len(self.children)})")
            if any(not lb for lb in self.labels):
                raise ValidationError("pane labels must be non-empty strings")
            dupes = sorted({lb for lb in self.labels if self.labels.count(lb) > 1})
            if dupes:
                raise ValidationError(f"pane labels must be unique; duplicated: {dupes}")
        self._freeze()

    def __add__(self, other: Node) -> Layout:
        if self.cells is not None or self.labels is not None:
            # a mosaic / named layout is a sealed shape — nest, don't append
            return Layout((self, other))
        return Layout(self.children + (other,), kind=self.kind, options=self.options,
                      backend_hint=self.backend_hint)

    def __getitem__(self, key: str | int) -> Node:
        """A child by explicit label (searching nested `Layout`s too) or by
        direct index. Only *given* labels resolve — default index labels are
        positional, so address those with the int form."""
        if isinstance(key, int):
            return self.children[key]
        found = self._find(key)
        if found is None:
            raise KeyError(f"no pane labeled {key!r} in this layout")
        return found

    def _find(self, label: str) -> Node | None:
        if self.labels is not None:
            for lb, child in zip(self.labels, self.children, strict=True):
                if lb == label:
                    return child
        for child in self.children:
            if isinstance(child, Layout):
                inner = child._find(label)
                if inner is not None:
                    return inner
        return None

    def with_pane(self, label: str, node: Node) -> Layout:
        """Copy-with: the layout with the pane named `label` replaced by
        `node` ([D145]) — the declarative way to update one pane
        (`view.set_root(root.with_pane("price", new_price))`). Searches nested
        `Layout`s; raises `KeyError` if the label is absent."""
        replaced = self._with_pane(label, node)
        if replaced is None:
            raise KeyError(f"no pane labeled {label!r} in this layout")
        return replaced

    def _with_pane(self, label: str, node: Node) -> Layout | None:
        if self.labels is not None and label in self.labels:
            children = tuple(node if lb == label else child
                             for lb, child in zip(self.labels, self.children, strict=True))
            return self.with_(children=children)
        for i, child in enumerate(self.children):
            if isinstance(child, Layout):
                inner = child._with_pane(label, node)
                if inner is not None:
                    children = self.children[:i] + (inner,) + self.children[i + 1:]
                    return self.with_(children=children)
        return None

    def __mul__(self, other: Node) -> Overlay:
        return Overlay((self, other))

    def opts(self, *,
             title: str | None | _Unset = UNSET,
             rows: int | None | _Unset = UNSET,
             cols: int | None | _Unset = UNSET,
             spacing: int | _Unset = UNSET,
             link_x: bool | str | _Unset = UNSET,
             link_y: bool | str | _Unset = UNSET,
             tab_labels: Sequence[str] | None | _Unset = UNSET,
             dock_areas: Mapping[int, str] | Sequence[tuple] | None | _Unset = UNSET,
             width_ratios: Sequence[float] | None | _Unset = UNSET,
             height_ratios: Sequence[float] | None | _Unset = UNSET) -> Layout:
        """Field-wise merge of the layout options (`title` here is the
        container suptitle). Only passed fields change; chains."""
        cur = self.options
        merged = LayoutOptions(
            rows=cur.rows if isinstance(rows, _Unset) else rows,
            cols=cur.cols if isinstance(cols, _Unset) else cols,
            spacing=cur.spacing if isinstance(spacing, _Unset) else spacing,
            link_x=cur.link_x if isinstance(link_x, _Unset) else link_x,
            link_y=cur.link_y if isinstance(link_y, _Unset) else link_y,
            tab_labels=cur.tab_labels if isinstance(tab_labels, _Unset) else tab_labels,
            dock_areas=cur.dock_areas if isinstance(dock_areas, _Unset) else dock_areas,
            title=cur.title if isinstance(title, _Unset) else title,
            width_ratios=(cur.width_ratios if isinstance(width_ratios, _Unset)
                          else width_ratios),
            height_ratios=(cur.height_ratios if isinstance(height_ratios, _Unset)
                           else height_ratios),
        )
        return Layout(self.children, kind=self.kind, options=merged,
                      backend_hint=self.backend_hint, cells=self.cells,
                      labels=self.labels)

    def __repr__(self) -> str:
        shown = {k: v for k, v in self.options._fields().items()
                 if v != getattr(LayoutOptions(), k)}
        inner = ", ".join(f"{k}={v!r}" for k, v in shown.items())
        return (f"Layout({len(self.children)} children, kind={self.kind!r}"
                + (f", {inner}" if inner else "") + ")")

    @classmethod
    def grid(cls, children: Sequence[Node] | Mapping[str, Node], *,
             cells: Mapping[str, Cell] | Sequence[Cell] | None = None,
             **kw) -> Layout:
        """A grid — from a sequence, or a mapping whose keys become the pane
        labels ([D145]). `cells=` places panes explicitly ([D148]) — the
        programmatic answer to spans, symmetric with the mosaic's output:

            Layout.grid({"ch0": a, "ch1": b, "summary": s},
                        cells={"ch0": (0, 0, 1, 1), "ch1": (1, 0, 1, 1),
                               "summary": (0, 1, 2, 1)})

        A `cells` mapping is keyed by label (mapping children required) and
        may reorder freely; a sequence aligns with the children. Overlap and
        span validity are checked like the mosaic parser's."""
        if isinstance(cells, Mapping):
            if not isinstance(children, Mapping):
                raise ValidationError(
                    "a cells mapping needs mapping children (label → node)")
            missing = [lb for lb in children if lb not in cells]
            extra = [lb for lb in cells if lb not in children]
            if missing or extra:
                raise ValidationError(
                    f"cells labels must match children labels exactly; "
                    f"missing={missing}, unknown={extra}")
            cells = [cells[lb] for lb in children]
        return cls(children, kind="grid", cells=cells, **kw)

    @classmethod
    def mosaic(cls, spec: MosaicSpec, mapping: Mapping[str, Node] | None = None,
               *, options: LayoutOptions | None = None,
               backend_hint: str | None = None, **panes: Node) -> Layout:
        """A grid from an ASCII plan (the `subplot_mosaic` precedent):

            Layout.mosaic("AAB\\nCCB", A=curve, B=sidebar, C=table)
            Layout.mosaic([["price",  "book"],
                           ["volume", "book"]], price=p, volume=v, book=ob)

        String form: each distinct character is one pane (spanning its
        rectangle); `.` is a hole. List form ([D145]): arbitrary string
        labels, `None` (or `"."`) a hole. Panes come as keywords or as a
        `mapping` (for labels that aren't identifiers); every label in the
        spec must be given, and vice versa. Labels are **retained** — they key
        state capture/restore, `view.pane(...)`, and `layout[label]`."""
        from ..errors import ValidationError  # noqa: PLC0415

        all_panes = {**(mapping or {}), **panes}
        cells_by_label = parse_mosaic(spec)
        missing = [lb for lb in cells_by_label if lb not in all_panes]
        extra = [k for k in all_panes if k not in cells_by_label]
        if missing or extra:
            raise ValidationError(
                f"mosaic panes must match the spec labels exactly; "
                f"missing={missing}, unknown={extra}")
        return cls([all_panes[lb] for lb in cells_by_label], kind="grid",
                   options=options, backend_hint=backend_hint,
                   cells=list(cells_by_label.values()),
                   labels=list(cells_by_label))

    @classmethod
    def tabs(cls, children, **kw) -> Layout:
        return cls(children, kind="tabs", **kw)

    @classmethod
    def splitter(cls, children, **kw) -> Layout:
        return cls(children, kind="splitter", **kw)


def link_groups(cells: Sequence[Cell], count: int, mode) -> list[list[int]]:
    """Child-index groups to axis-link ([D146]), from the same `cells` that
    decide grid shape. `False` → none; `True` → one group of all; `"col"` /
    `"row"` → connected components of children sharing a column/row — a
    spanning pane joins every column/row it covers (the `subplot_mosaic`
    sharing rule), transitively merging groups. Only groups of 2+ return."""
    if mode is False or count < 2:
        return []
    if mode is True:
        return [list(range(count))]
    parent = list(range(count))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    seen: dict[int, int] = {}  # column (or row) index → first child covering it
    for i, (r, c, rs, cs) in enumerate(cells[:count]):
        span = range(c, c + cs) if mode == "col" else range(r, r + rs)
        for k in span:
            if k in seen:
                union(i, seen[k])
            else:
                seen[k] = i
    groups: dict[int, list[int]] = {}
    for i in range(count):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def flat_pane_labels(node: Node) -> tuple[str, ...]:
    """The effective pane labels of a render, flattened depth-first in child
    order ([D145]/[D150]) — the single source of pane identity shared by state
    capture/restore, `view.pane(...)`, and event scoping. Each Element/Overlay
    leaf is one pane: a *given* label if its parent `Layout` names it, else its
    flat index as a string. A label on a `Layout` child names the subtree for
    `layout[...]`/`with_pane`, not a pane. Labels must be unique across the
    whole tree — collisions (incl. a given label shadowing another pane's
    default index label) raise `ValidationError`."""
    from ..errors import ValidationError  # noqa: PLC0415

    given: list[str | None] = []

    def leaf(n: Node, lb: str | None) -> None:
        given.append(lb)  # the surface itself …
        kids = n.children if isinstance(n, Overlay) else (n,)
        for el in kids:  # … then its insets, in child order ([D152]/[D153])
            if getattr(el, "STRUCTURAL_CHILD", None):
                given.append(getattr(el, "label", None))

    def walk(n: Node) -> None:
        if isinstance(n, Layout):
            labels = n.labels or (None,) * len(n.children)
            for child, lb in zip(n.children, labels, strict=True):
                if isinstance(child, Layout):
                    walk(child)
                else:
                    leaf(child, lb)
        else:
            leaf(n, None)

    walk(node)
    out = [lb if lb is not None else str(i) for i, lb in enumerate(given)]
    dupes = sorted({lb for lb in out if out.count(lb) > 1})
    if dupes:
        raise ValidationError(
            f"pane labels must be unique across the layout tree; duplicated: "
            f"{dupes} (a given label may also collide with an unlabeled pane's "
            f"default index label)")
    return tuple(out)


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
        # chrome: annotations and structural elements (an Inset, [D152]) take
        # no palette slot and don't shift the series that follow
        if isinstance(el, ANNOTATION_TYPES) or getattr(el, "STRUCTURAL_CHILD", None):
            out.append(0)
        else:
            out.append(i)
            i += 1
    return out


def _elements_of(node: Node) -> Iterator[Element]:
    if isinstance(node, Element):
        yield node
        if node.STRUCTURAL_CHILD is not None:  # [D152]: an Inset's contents
            yield from _elements_of(getattr(node, node.STRUCTURAL_CHILD))
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
    if node.STRUCTURAL_CHILD is not None:  # [D152]: an Inset's contents render
        child = getattr(node, node.STRUCTURAL_CHILD)  # on the SAME surface —
        inner = negotiate(child, view_backend, ancestor_hint=chosen)
        if inner != chosen:  # — so the same backend, like overlay children
            raise IncompatibleOverlayError(
                f"an inset renders on its parent's surface; its contents "
                f"resolve to {inner!r} but the surface is {chosen!r}")
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

    if getattr(node, "STRUCTURAL_CHILD", None):  # [D152]: intersect over contents
        elems = list(_elements_of(node))
        candidates = [b for b in backends.registered()
                      if all(b.supports(type(e)) for e in elems)]
        if not candidates:
            raise NoBackendForError(
                "no single backend supports the inset and its contents: "
                f"{sorted({type(e).__name__ for e in elems})}")
        return _pick(candidates, max((_data_size(e) or 0) for e in elems))
    candidates = [b for b in backends.registered() if b.supports(type(node))]
    if not candidates:
        raise NoBackendForError(f"no registered backend supports {type(node).__name__}")
    return _pick(candidates, _data_size(node))


def _pick(candidates, n: int | None) -> str:
    from .. import backends

    if n is not None and n > 1_000_000:
        return max(candidates, key=lambda b: b.capabilities.max_recommended_points).name
    return max(candidates, key=lambda b: -backends.priority_index(b.name)).name
