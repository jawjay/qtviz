"""`Element` — pure declarative plot data (spec §2.1).

Knows its data, channel bindings, options, identity; knows nothing about
rendering. Immutable, value-hashed, Qt-free. Channels bind to **accessors**
(`str | Expression | Callable | ArrayLike`, D14); `channels()` maps each fixed
role to its accessor, and the resolve pipeline turns those into role-keyed
arrays the renderer reads.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..data import GriddedRef, TabularRef, accessor_columns
from ..errors import ValidationError
from ._immutable import Immutable

ElementId = str


def _next_element_id() -> ElementId:
    return uuid.uuid4().hex


def require_gridded(ref, *, who: str) -> None:
    if not isinstance(ref, GriddedRef):
        raise TypeError(f"{who} requires gridded (N-D array) data, not tabular")


def validate_channels(data, channels: dict, *, who: str) -> None:
    """Schema-validate the *introspectable* accessors (str / Expression) at
    construction; callables defer to first resolve."""
    if not isinstance(data, TabularRef):
        raise TypeError(f"{who} requires tabular data with named columns")
    have = set(data.schema().names)
    for accessor in channels.values():
        cols = accessor_columns(accessor)
        if cols is None:  # callable — opaque, validated at resolve
            continue
        missing = [c for c in cols if c not in have]
        if missing:
            raise ValidationError(
                f"{who}: column(s) {sorted(missing)} not in data; available: {sorted(have)}"
            )


class Element(Immutable):
    # [D124] one data contract: every element resolves `.data` (a class-level
    # `None` covers the data-less annotation class, so consumers write
    # `node.data`, never `getattr(node, "data", None)`), and `DATA_KIND`
    # declares how it consumes data — the resolve pipeline dispatches on it.
    data: Any = None
    DATA_KIND: str = "tabular"  # "tabular" | "gridded" | "none"
    # [D152] declared (never duck-typed) marker for a data-less *structural*
    # element that carries a child NODE under this field name (Inset.child):
    # the resolve pipeline recurses into it and negotiation intersects over
    # its elements.
    STRUCTURAL_CHILD: str | None = None
    REQUIRED_OPTIONS: tuple[str, ...] = ()
    RECOMMENDED_OPTIONS: tuple[str, ...] = ()
    # Fixed channel roles bound to accessors; default role == field name.
    CHANNELS: tuple[str, ...] = ()
    # [D123] honesty declarations: `HONORED_BY_LOWERING` sits beside `lower()`
    # and is proven by the perturbation guard (tests/qtviz/test_marks.py);
    # `HONORED_NATIVE` is the set every native renderer honors, from which a
    # backend subtracts its declared deltas (HONORED_DELTAS). One declaration,
    # in core — the triplicated per-backend tables are gone.
    HONORED_BY_LOWERING: frozenset[str] = frozenset()
    HONORED_NATIVE: frozenset[str] = frozenset()

    def __init__(self, *, backend_hint: str | None = None, id: ElementId | None = None) -> None:
        self.backend_hint = backend_hint
        self.id = id or _next_element_id()

    def channels(self) -> dict:
        """`{role: accessor}` — what the resolve pipeline materializes into
        role-keyed arrays. Override for non-uniform shapes (e.g. ErrorBars)."""
        return {role: getattr(self, role) for role in self.CHANNELS}

    def _validate_tabular(self) -> None:
        validate_channels(self.data, self.channels(), who=type(self).__name__)

    def legend_entry(self, theme, index: int = 0):
        """This element's contribution to a multi-series legend ([D60]): its
        `label` + swatch, or `None` when it shouldn't contribute (no `label`, or —
        per override — it already emits its own `Legend`, like a `color_by`
        Scatter). `index` is the element's position in its Overlay, which decides
        the default palette slot exactly as the renderers do."""
        label = getattr(self, "label", None)
        if label is None:
            return None
        from .color import Color  # noqa: PLC0415 — element stays import-light
        from .encoding import LegendEntry  # noqa: PLC0415

        spec = getattr(self, "color", None)
        swatch = Color(spec) if spec is not None else theme.palette[index % len(theme.palette)]
        return LegendEntry(str(label), swatch)

    def lower(self, ctx):
        """This element's Mark lowering ([D122]) — `Lowered | None`. `None`
        (the default) means the element does not lower: every backend must
        register a native renderer for it, and `type(el).lower is not
        Element.lower` is the dispatch predicate backends use. Overrides run
        on *resolved* data and must be pure: marks in linear data space
        ([D121]), style resolved through `ctx`. A registered native renderer
        wins over lowering (the fast-path override)."""
        return None

    def select_xy(self):
        """Brush/pick registration coordinates `(x, y) | None` for elements a
        backend wires natively ([D124] — the declared replacement for
        isinstance tuples in backend event code). Lowered elements carry this
        on `Lowered.select_xy` instead."""
        return None

    def _replace_data(self, ref):
        """Low-level copy with `data` swapped (no re-validation) — used by the
        resolve pipeline to install the role-keyed eager ref. Marks the copy
        resolved so a later `resolve_node` (e.g. inside backend.render) is a
        no-op rather than re-resolving against the role-keyed ref."""
        obj = object.__new__(type(self))
        for k, v in vars(self).items():
            object.__setattr__(obj, k, v)
        object.__setattr__(obj, "data", ref)
        object.__setattr__(obj, "_resolved", True)
        return obj

    def opts(self, **kw):
        """[D133] surface configuration without abandoning the algebra:
        `el.opts(title=…, x="t [s]", y=AxisSpec(scale="log"))` wraps this
        element in a one-child `Overlay` carrying the options — the exact
        `Overlay([el], options=…)` construction, as sugar. Accepts the
        `OverlayOptions` keywords (`title`, `x`, `y`, `y2`, `aspect`,
        `legend`, `background`, `grid`); `x`/`y`/`y2` take a label string or
        an `AxisSpec`. Chain on the result to refine."""
        from .compose import Overlay  # noqa: PLC0415
        from .options import OverlayOptions  # noqa: PLC0415

        try:
            options = OverlayOptions(**kw)
        except TypeError:
            import difflib  # noqa: PLC0415
            import inspect  # noqa: PLC0415

            from ..errors import ValidationError  # noqa: PLC0415

            valid = [p for p in inspect.signature(OverlayOptions.__init__).parameters
                     if p != "self"]
            bad = sorted(set(kw) - set(valid))
            if not bad:
                raise  # a genuine TypeError from a valid keyword's value
            hints = [difflib.get_close_matches(b, valid, n=1) for b in bad]
            close = [h[0] for h in hints if h]
            mean = f"; did you mean {', '.join(repr(c) for c in close)}?" if close else ""
            raise ValidationError(
                f"{type(self).__name__}.opts(): unknown option(s) "
                f"{', '.join(repr(b) for b in bad)}{mean} (valid: {', '.join(valid)})"
            ) from None
        return Overlay((self,), options=options)

    # composition operators — lazy imports avoid an element↔compose cycle
    def __mul__(self, other):
        from .compose import Overlay

        return Overlay((self, other))

    def __add__(self, other):
        from .compose import Layout

        return Layout((self, other))

    def over(self, other):
        return self.__mul__(other)
