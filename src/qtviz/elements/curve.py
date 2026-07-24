"""Curve element (spec §5.2)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Curve(Element):
    """A connected line through ordered x/y points."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "alpha", "label")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        line_style: Literal["solid", "dashed", "dotted", "dashdot"] = "solid",
        alpha: float = 1.0,
        label: str | None = None,
        scale: Literal["native", "auto", "datashader"] = "native",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Curve")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.alpha = alpha
        self.label = label
        self.scale = scale
        self._validate_tabular()
        self._freeze()
