"""Area element — filled series, layered or stacked (parity increment 3)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha, check_color, check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element, ElementId
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError

_MODES = ("overlay", "stacked")


class Area(Element):
    """A series filled to the zero baseline. With `by=` each distinct group
    value becomes its own palette-colored band — layered translucently
    (`mode="overlay"`) or cumulatively stacked (`"stacked"`) — the shared
    grouping pattern, so stacking stays inside one element. Grouped data pivots
    on unique x (duplicate rows in a group sum, like `Bars`)."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("by", "mode", "color", "alpha", "label", "axis")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "by", "color", "label", "mode"})
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        by: Accessor | None = None,  # full accessor union — never just a column name
        mode: Literal["overlay", "stacked"] = "overlay",
        color: ColorSpec | None = None,
        alpha: float = 0.6,
        label: str | None = None,
        axis: str = "y",
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if mode not in _MODES:
            raise ValidationError(f"Area mode must be one of {_MODES}, got {mode!r}")
        if mode != "overlay" and by is None:
            raise ValidationError(f"Area mode={mode!r} requires by= (it stacks the groups)")
        check_exclusive(color, by, names=("color", "by"), who="Area")
        check_alpha(alpha, who="Area")
        check_color(color, who="Area")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.by = by
        self.mode = mode
        self.color = color
        self.alpha = alpha
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_axis(axis, "native", who="Area")
        self.label = label
        self.axis = axis
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"x": self.x, "y": self.y}
        if self.by is not None:
            ch["by"] = self.by
        return ch
