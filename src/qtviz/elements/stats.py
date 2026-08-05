"""Statistical elements — BoxPlot + Violin ([D67], milestone-0.4 §4).

Both reduce a raw `value` column through the shared `core/_stats` implementations
(`box_stats`, `kde`) at render, so every backend draws the *same* numbers —
the statistics definition is qtviz's, never the engine's. `by=` splits into
one box/violin per category, palette-colored in `np.unique` order (the same
swatch rule as `color_by`).
"""

from __future__ import annotations

from ..core._validate import check_alpha, check_color, check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class _Distribution(Element):
    """Shared shape: a raw `value` column, an optional `by` category split."""

    REQUIRED_OPTIONS = ("value",)
    RECOMMENDED_OPTIONS = ("by", "color", "alpha", "label")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "by", "color", "label"})

    def __init__(
        self,
        data: DataLike,
        *,
        value: Accessor,
        by: Accessor | None = None,  # full accessor union — never just a column name
        color: ColorSpec | None = None,
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_exclusive(color, by, names=("color", "by"), who=type(self).__name__)
        check_alpha(alpha, who=type(self).__name__)
        check_color(color, who=type(self).__name__)
        self.data = as_data_ref(data)
        self.value = value
        self.by = by
        self.color = color
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"value": self.value}
        if self.by is not None:
            ch["by"] = self.by
        return ch


class BoxPlot(_Distribution):
    """A five-number-summary box (median, quartiles, 1.5·IQR whiskers clipped to
    the data, outlier points) of `value` — one box, or one per `by` category."""


class Violin(_Distribution):
    """A kernel-density silhouette of `value` (Gaussian KDE, Scott's rule) —
    one violin, or one per `by` category."""

    # [D129]: explicit signature — the `*args, **kw` opacity (nothing in
    # `help()`/IDE completion) was a diagnosed 1.x wart.
    def __init__(
        self,
        data: DataLike,
        *,
        value: Accessor,
        by: Accessor | None = None,
        color: ColorSpec | None = None,
        alpha: float = 0.6,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(data, value=value, by=by, color=color, alpha=alpha,
                         label=label, backend_hint=backend_hint, id=id)
