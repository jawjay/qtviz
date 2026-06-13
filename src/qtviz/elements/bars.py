"""Bars element (spec §5.3)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element, require_tabular_columns
from ..data import as_data_ref


class Bars(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("group", "color", "orient")

    def __init__(
        self,
        data,
        *,
        x: str,
        y: str,
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
        require_tabular_columns(self.data, [x, y, group], who="Bars")
        self._freeze()
