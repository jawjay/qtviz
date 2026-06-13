"""Curve element (spec §5.2)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element, require_tabular_columns
from ..data import as_data_ref


class Curve(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "alpha")

    def __init__(
        self,
        data,
        *,
        x: str,
        y: str,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        line_style: Literal["solid", "dashed", "dotted", "dashdot"] = "solid",
        alpha: float = 1.0,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.alpha = alpha
        require_tabular_columns(self.data, [x, y], who="Curve")
        self._freeze()
