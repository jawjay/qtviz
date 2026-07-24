"""Statistical elements — BoxPlot + Violin ([D67], milestone-0.4 §4).

Both reduce a raw `column` through the shared `core/_stats` implementations
(`box_stats`, `kde`) at render, so every backend draws the *same* numbers —
the statistics definition is qtviz's, never the engine's. `by=` splits into
one box/violin per category, palette-colored in `np.unique` order (the same
swatch rule as `color_by`).
"""

from __future__ import annotations

from ..core._validate import check_alpha, check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class _Distribution(Element):
    """Shared shape: a raw `column`, an optional `by` category split."""

    REQUIRED_OPTIONS = ("column",)
    RECOMMENDED_OPTIONS = ("by", "color", "alpha", "label")

    def __init__(
        self,
        data: DataLike,
        *,
        column: Accessor,
        by: str | None = None,
        color: ColorSpec | None = None,
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_exclusive(color, by, names=("color", "by"), who=type(self).__name__)
        check_alpha(alpha, who=type(self).__name__)
        self.data = as_data_ref(data)
        self.column = column
        self.by = by
        self.color = color
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"column": self.column}
        if self.by is not None:
            ch["by"] = self.by
        return ch


class BoxPlot(_Distribution):
    """A five-number-summary box (median, quartiles, 1.5·IQR whiskers clipped to
    the data, outlier points) of `column` — one box, or one per `by` category."""


class Violin(_Distribution):
    """A kernel-density silhouette of `column` (Gaussian KDE, Scott's rule) —
    one violin, or one per `by` category."""

    def __init__(self, *args, alpha: float = 0.6, **kw) -> None:
        super().__init__(*args, alpha=alpha, **kw)
