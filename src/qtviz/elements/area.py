"""Area element — filled series, layered or stacked ([D84b], parity increment 3)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha, check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError

_MODES = ("overlay", "stacked")


class Area(Element):
    """A series filled to the zero baseline. With `group=` each distinct group
    value becomes its own palette-colored band — layered translucently
    (`mode="overlay"`) or cumulatively stacked (`"stacked"`) — the [D68]
    grouping pattern, so stacking stays inside one element. Grouped data pivots
    on unique x (duplicate rows in a group sum, like `Bars`)."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("group", "mode", "color", "alpha", "label")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        group: str | None = None,
        mode: Literal["overlay", "stacked"] = "overlay",
        color: ColorSpec | None = None,
        alpha: float = 0.6,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if mode not in _MODES:
            raise ValidationError(f"Area mode must be one of {_MODES}, got {mode!r}")
        if mode != "overlay" and group is None:
            raise ValidationError(f"Area mode={mode!r} requires group= (it stacks the groups)")
        check_exclusive(color, group, names=("color", "group"), who="Area")
        check_alpha(alpha, who="Area")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.group = group
        self.mode = mode
        self.color = color
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"x": self.x, "y": self.y}
        if self.group is not None:
            ch["group"] = self.group
        return ch
