"""Spread element — filled band between two y-series (spec §5.8)."""

from __future__ import annotations

from ..core.color import ColorSpec
from ..core.element import Element, require_tabular_columns
from ..data import as_data_ref


class Spread(Element):
    REQUIRED_OPTIONS = ("x", "y_lo", "y_hi")
    RECOMMENDED_OPTIONS = ("color", "alpha")

    def __init__(
        self,
        data,
        *,
        x: str,
        y_lo: str,
        y_hi: str,
        color: ColorSpec | None = None,
        alpha: float = 0.3,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self.data = as_data_ref(data)
        self.x, self.y_lo, self.y_hi = x, y_lo, y_hi
        self.color = color
        self.alpha = alpha
        require_tabular_columns(self.data, [x, y_lo, y_hi], who="Spread")
        self._freeze()
