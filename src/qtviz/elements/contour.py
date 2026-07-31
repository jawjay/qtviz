"""Contour element — iso-lines over a 2-D grid ([D89], parity increment 6)."""

from __future__ import annotations

from collections.abc import Sequence

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref
from ..errors import ValidationError


class Contour(Element):
    """Iso-value contours of a 2-D array over explicit `bounds` (the `Image`
    data contract). `levels` is a count (uniform interior levels, computed once
    in core so every backend draws the same lines — [D67]) or an explicit
    sequence of values. `filled=True` shades between levels; pyqtgraph draws
    lines only and warns on `filled` (capability-honest)."""

    REQUIRED_OPTIONS = ("bounds",)
    RECOMMENDED_OPTIONS = ("levels", "filled", "colormap", "line_width", "label")

    def __init__(
        self,
        data: DataLike,
        *,
        bounds: tuple[float, float, float, float],
        levels: int | Sequence[float] = 10,
        filled: bool = False,
        colormap: str = "viridis",
        line_width: float = 1.5,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if isinstance(levels, bool) or (isinstance(levels, int) and levels < 1):
            raise ValidationError(f"Contour levels must be a positive int or a "
                                  f"sequence of values, got {levels!r}")
        if not isinstance(levels, int):
            levels = tuple(float(v) for v in levels)
            if not levels:
                raise ValidationError("Contour levels sequence must be non-empty")
        self.data = as_data_ref(data)
        self.bounds = tuple(float(b) for b in bounds)
        self.levels = levels
        self.filled = bool(filled)
        self.colormap = colormap
        self.line_width = line_width
        self.label = label
        require_gridded(self.data, who="Contour")
        self._freeze()
