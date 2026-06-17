"""Bars element (spec §5.3)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Bars(Element):
    """Bars — `x` categories (or numeric positions) with `y` heights."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("group", "color", "orient")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        group: str | None = None,
        orient: Literal["v", "h"] = "v",
        color: ColorSpec | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.group = group
        self.orient = orient
        self.color = color
        self._validate_tabular()
        self._freeze()
