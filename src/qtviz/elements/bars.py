"""Bars element (spec §5.3)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError

_MODES = ("grouped", "stacked")


class Bars(Element):
    """Bars — `x` categories (or numeric positions) with `y` heights. With
    `by=` each distinct group value becomes its own palette-colored series,
    laid out side-by-side (`mode="grouped"`) or cumulatively (`"stacked"`);
    `mode` is meaningful only with `by`."""

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
        annotate: bool | str = False,
        alpha: float = 1.0,
        label: str | None = None,
        axis: Literal["y", "y2"] = "y",
        backend_hint: str | None = None,
        id=None,
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
        # [D131] union: True ≡ "auto", False ≡ off, a format spec picks the text
        annotate_spec: str | None = (
            "auto" if annotate is True else None if annotate is False else annotate)
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
        self.annotate = annotate_spec
        self.alpha = float(alpha)
        self.label = label
        self.axis = axis
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        """x/y always; the `by` role when set, so the resolve pipeline
        materializes the category column for the renderers (same pattern as
        Scatter's `color_by`)."""
        ch = {"x": self.x, "y": self.y}
        if self.by is not None:
            ch["by"] = self.by
        if self.color_by is not None:
            ch["color"] = self.color_by
        return ch

    def legend_entry(self, theme, index: int = 0):
        """A `color_by` Bars emits its own key ([D60] risk #3 rule)."""
        if self.color_by is not None:
            return None
        return super().legend_entry(theme, index)
