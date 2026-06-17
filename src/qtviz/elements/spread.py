"""Spread element — filled band between two y-series (spec §5.8)."""

from __future__ import annotations

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Spread(Element):
    """A filled band between `y_lo` and `y_hi` (e.g. a confidence interval)."""

    REQUIRED_OPTIONS = ("x", "y_lo", "y_hi")
    RECOMMENDED_OPTIONS = ("color", "alpha")
    CHANNELS = ("x", "y_lo", "y_hi")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y_lo: Accessor,
        y_hi: Accessor,
        color: ColorSpec | None = None,
        alpha: float = 0.3,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Spread")
        self.data = as_data_ref(data)
        self.x, self.y_lo, self.y_hi = x, y_lo, y_hi
        self.color = color
        self.alpha = alpha
        self._validate_tabular()
        self._freeze()
