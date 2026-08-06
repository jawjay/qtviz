"""Bars element (spec §5.3)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element, ElementId
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError

_MODES = ("grouped", "stacked")


class Bars(Element):
    """Bars — `x` categories (or numeric positions) with `y` heights. With
    `by=` each distinct group value becomes its own palette-colored series,
    laid out side-by-side (`mode="grouped"`) or cumulatively (`"stacked"`);
    `mode` is meaningful only with `by`.

    `annotate=` is the [D131] union: `True` labels each bar with its value
    (`"auto"` → `%g`), a `str` is a [D86] format spec for that value, and a
    **non-str accessor** (`col()` expression, callable, or raw array) labels
    each bar from the data instead ([D136] accessor arm) — the one place the
    accessor union's plain-string form is taken by the format spec, so a
    column label is spelled `annotate=col("name")`."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("by", "mode", "color", "color_by", "orient",
                           "annotate", "alpha", "label", "axis")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"annotate", "by", "color", "color_by", "label", "mode", "orient"})
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        by: Accessor | None = None,  # full accessor union — never just a column name
        mode: Literal["grouped", "stacked"] = "grouped",
        orient: Literal["vertical", "horizontal"] = "vertical",
        color: ColorSpec | None = None,
        color_by: Accessor | None = None,
        annotate: bool | str | Accessor = False,
        alpha: float = 1.0,
        label: str | None = None,
        axis: Literal["y", "y2"] = "y",
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from ..core._validate import check_alpha, check_color  # noqa: PLC0415
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_alpha(alpha, who="Bars")
        check_color(color, who="Bars")
        check_axis(axis, "native", who="Bars")
        if mode not in _MODES:
            raise ValidationError(f"Bars mode must be one of {_MODES}, got {mode!r}")
        from ..core._validate import check_choice  # noqa: PLC0415

        check_choice(orient, ("vertical", "horizontal"), who="Bars", param="orient")
        if mode != "grouped" and by is None:
            raise ValidationError(f"Bars mode={mode!r} requires by= (it stacks the groups)")
        # [D131] union: True ≡ "auto", False ≡ off, a format spec picks the text;
        # [D136] accessor arm: a non-str accessor labels bars from the data.
        # One stored field (`self.annotate`) holds whichever arm — the
        # `_fields()` round-trip contract wants exactly the constructor kwarg.
        annotate_spec: str | None = None
        annotate_acc: Accessor | None = None
        if annotate is None or isinstance(annotate, bool):
            annotate_spec = "auto" if annotate is True else None
        elif isinstance(annotate, str):
            annotate_spec = annotate
        else:
            annotate_acc = annotate
            if by is not None:
                raise ValidationError(
                    "Bars(annotate=<accessor>) labels per data row, but by= "
                    "aggregates rows into bars — the label source would be "
                    "ambiguous. Use a format-spec annotate= with by=.")
        if annotate_spec is not None:  # value labels format via the [D86] vocabulary
            from ..core._ticks import validate_tick_format  # noqa: PLC0415

            validate_tick_format(annotate_spec, who="Bars(annotate=)")
        check_exclusive(color, by, names=("color", "by"), who="Bars")
        check_exclusive(color, color_by, names=("color", "color_by"), who="Bars")
        check_exclusive(by, color_by, names=("by", "color_by"), who="Bars")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.by = by
        self.mode = mode
        self.orient = orient
        self.color = color
        self.color_by = color_by
        self.annotate = annotate_acc if annotate_acc is not None else annotate_spec
        self.alpha = float(alpha)
        self.label = label
        self.axis = axis
        self._validate_tabular()
        self._freeze()

    @property
    def annotate_by(self) -> Accessor | None:
        """The [D136] accessor arm of `annotate=` — `None` when annotate is
        off or a format spec (the fmt arm stays on `.annotate` as a str)."""
        a = self.annotate
        return None if a is None or isinstance(a, str) else a

    def channels(self) -> dict:
        """x/y always; the `by` role when set, so the resolve pipeline
        materializes the category column for the renderers (same pattern as
        Scatter's `color_by`)."""
        ch = {"x": self.x, "y": self.y}
        if self.by is not None:
            ch["by"] = self.by
        if self.color_by is not None:
            ch["color"] = self.color_by
        if self.annotate_by is not None:  # [D136]: materialized like any channel
            ch["annotate"] = self.annotate_by
        return ch

    def legend_entry(self, theme, index: int = 0):
        """A `color_by` Bars emits its own key ([D60] risk #3 rule)."""
        if self.color_by is not None:
            return None
        return super().legend_entry(theme, index)
