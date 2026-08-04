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
    laid out side-by-side (`mode="grouped"`) or cumulatively (`"stacked"`)
    ([D68]); `mode` is meaningful only with `by`."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("by", "mode", "color", "color_by", "orient",
                           "bar_labels", "label")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        by: Accessor | None = None,  # full accessor union — never just a column name
        mode: Literal["grouped", "stacked"] = "grouped",
        orient: Literal["v", "h"] = "v",
        color: ColorSpec | None = None,
        color_by: str | None = None,
        bar_labels: str | None = None,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if mode not in _MODES:
            raise ValidationError(f"Bars mode must be one of {_MODES}, got {mode!r}")
        if mode != "grouped" and by is None:
            raise ValidationError(f"Bars mode={mode!r} requires by= (it stacks the groups)")
        if bar_labels is not None:  # value labels format via the [D86] vocabulary
            from ..core._ticks import validate_tick_format  # noqa: PLC0415

            validate_tick_format(bar_labels, who="Bars(bar_labels=)")
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
        self.bar_labels = bar_labels
        self.label = label
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
