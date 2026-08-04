"""Contour element — iso-lines over a 2-D grid ([D89], parity increment 6)."""

from __future__ import annotations

from collections.abc import Sequence

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref
from ..errors import ValidationError


class Contour(Element):
    """Iso-value contours of a 2-D array over explicit `extent` (the `Image`
    data contract). `levels` is a count (uniform interior levels, computed once
    in core so every backend draws the same lines — [D67]) or an explicit
    sequence of values. `filled=True` shades between levels; pyqtgraph draws
    lines only and warns on `filled` (capability-honest).

    `labels=` ([D117]) writes each level's value inline on its longest
    iso-line — `True` for `%g`, or any [D86] format spec. Placement (marching
    squares → arc-length midpoint, tangent angle normalized upright, and a
    background mask segment that breaks the line) is computed once in core,
    so every backend places identical labels — deliberately *not* mpl's
    native `clabel` ([D110] over engine fidelity)."""

    DATA_KIND = "gridded"  # [D124]
    REQUIRED_OPTIONS = ("extent",)
    RECOMMENDED_OPTIONS = ("levels", "filled", "colormap", "line_width", "label",
                           "labels")

    def __init__(
        self,
        data: DataLike,
        *,
        extent: tuple[float, float, float, float],
        levels: int | Sequence[float] = 10,
        filled: bool = False,
        colormap: str = "viridis",
        line_width: float = 1.5,
        label: str | None = None,
        labels: bool | str = False,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if isinstance(labels, str):
            from ..core._ticks import validate_tick_format  # noqa: PLC0415

            validate_tick_format(labels, who="Contour(labels=)")
        if isinstance(levels, bool) or (isinstance(levels, int) and levels < 1):
            raise ValidationError(f"Contour levels must be a positive int or a "
                                  f"sequence of values, got {levels!r}")
        if not isinstance(levels, int):
            levels = tuple(float(v) for v in levels)
            if not levels:
                raise ValidationError("Contour levels sequence must be non-empty")
        self.data = as_data_ref(data)
        self.extent = tuple(float(b) for b in extent)
        self.levels = levels
        self.filled = bool(filled)
        self.colormap = colormap
        self.line_width = line_width
        self.label = label
        self.labels = labels
        require_gridded(self.data, who="Contour")
        self._freeze()

    def resolved_labels(self):
        """The core-placed inline labels ([D117]), or `[]` when off — one
        call site per backend renderer."""
        if self.labels is False:
            return []
        import numpy as np  # noqa: PLC0415

        from ..core._stats import contour_label_specs, contour_levels  # noqa: PLC0415

        values = np.asarray(self.data.grid().values, dtype="float64")
        lv = contour_levels(values, self.levels)
        return contour_label_specs(values, lv, self.extent, spec=self.labels)
