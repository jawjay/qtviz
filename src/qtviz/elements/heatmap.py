"""Heatmap element — tabular x/y/z pivoted to a grid (spec §5.5)."""

from __future__ import annotations

from typing import Literal

from ..core._stats import GRID_AGGS
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Heatmap(Element):
    """A grid of tidy x/y cells shaded by a `z` value. Duplicate rows landing on
    one cell reduce through `aggregator` ([D69]; the pre-0.4 implicit behavior
    was `"last"`, kept in the vocabulary).

    `cell_labels=` ([D113]) writes each aggregated value at its cell center —
    `"auto"` for `%g`, or any [D86] format spec (`".1f"`, `"{:.0%}"`, …). The
    text color is computed in core per cell (WCAG luminance of the cell's ramp
    color → theme foreground or background), and grids above ~400 cells warn
    and skip labels rather than smear unreadable text."""

    REQUIRED_OPTIONS = ("x", "y", "z")
    RECOMMENDED_OPTIONS = ("colormap", "aggregator", "norm", "vmin", "vmax", "gamma",
                           "cell_labels")
    CHANNELS = ("x", "y", "z")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        z: Accessor,
        colormap: str = "viridis",
        aggregator: Literal["mean", "sum", "count", "max", "min", "last"] = "mean",
        norm: Literal["linear", "log", "power"] = "linear",
        vmin: float | None = None,
        vmax: float | None = None,
        gamma: float = 1.0,
        cell_labels: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from .image import check_norm  # noqa: PLC0415 — shared [D105] guard

        if aggregator not in GRID_AGGS:
            raise ValidationError(
                f"aggregator must be one of {GRID_AGGS}, got {aggregator!r}"
            )
        check_norm(norm, vmin, vmax, gamma, who="Heatmap")
        if cell_labels is not None and cell_labels != "auto":
            from ..core._ticks import validate_tick_format  # noqa: PLC0415

            validate_tick_format(cell_labels, who="Heatmap(cell_labels=)")
        self.data = as_data_ref(data)
        self.x, self.y, self.z = x, y, z
        self.colormap = colormap
        self.aggregator = aggregator
        self.norm = norm
        self.vmin = float(vmin) if vmin is not None else None
        self.vmax = float(vmax) if vmax is not None else None
        self.gamma = float(gamma)
        self.cell_labels = cell_labels
        self._validate_tabular()
        self._freeze()

    def resolved_cell_labels(self, xs, ys, grid, theme):
        """The core-computed labels ([D113]) for an already-pivoted grid, or
        `[]` when the option is off — one call site per backend renderer."""
        if self.cell_labels is None:
            return []
        from ..core.encoding import heatmap_cell_labels  # noqa: PLC0415

        return heatmap_cell_labels(
            xs, ys, grid, spec=self.cell_labels, norm=self.norm,
            vmin=self.vmin, vmax=self.vmax, gamma=self.gamma,
            colormap=self.colormap,
            foreground=theme.foreground, background=theme.background)
