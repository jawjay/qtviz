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
    `group=` each distinct group value becomes its own palette-colored series,
    laid out side-by-side (`mode="grouped"`) or cumulatively (`"stacked"`)
    ([D68]); `mode` is meaningful only with `group`."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("group", "color", "orient", "label")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        group: str | None = None,
        mode: Literal["grouped", "stacked"] = "grouped",
        orient: Literal["v", "h"] = "v",
        color: ColorSpec | None = None,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if mode not in _MODES:
            raise ValidationError(f"Bars mode must be one of {_MODES}, got {mode!r}")
        check_exclusive(color, group, names=("color", "group"), who="Bars")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.group = group
        self.mode = mode
        self.orient = orient
        self.color = color
        self.label = label
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        """x/y always; the `group` role when set, so the resolve pipeline
        materializes the group column for the renderers (same pattern as
        Scatter's `color_by`)."""
        ch = {"x": self.x, "y": self.y}
        if self.group is not None:
            ch["group"] = self.group
        return ch
