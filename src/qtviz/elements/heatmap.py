"""Heatmap element — tabular x/y/z pivoted to a grid (spec §5.5)."""

from __future__ import annotations

from typing import Literal

from ..core._stats import GRID_AGGS
from ..core.element import Element
from ..core.encoding import Norm
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError
from ._norm import NormedRaster, check_norm_clim


class Heatmap(NormedRaster, Element):
    """A grid of tidy x/y cells shaded by a `z` value. Duplicate rows landing on
    one cell reduce through `aggregator` ([D69]; the pre-0.4 implicit behavior
    was `"last"`, kept in the vocabulary).

    `annotate=` ([D113]) writes each aggregated value at its cell center —
    `"auto"` for `%g`, or any [D86] format spec (`".1f"`, `"{:.0%}"`, …). The
    text color is computed in core per cell (WCAG luminance of the cell's ramp
    color → theme foreground or background), and grids above ~400 cells warn
    and skip labels rather than smear unreadable text."""

    REQUIRED_OPTIONS = ("x", "y", "z")
    RECOMMENDED_OPTIONS = ("colormap", "aggregator", "norm", "clim",
                           "annotate")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"aggregator", "annotate", "clim", "colormap", "norm"})
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
        norm: str | Norm = "linear",
        clim: tuple[float | None, float | None] | None = None,
        annotate: bool | str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        
        if aggregator not in GRID_AGGS:
            raise ValidationError(
                f"aggregator must be one of {GRID_AGGS}, got {aggregator!r}"
            )
        self.norm, self.clim = check_norm_clim(norm, clim, who="Heatmap")
        # [D131] union: True ≡ "auto", False ≡ off, a format spec picks the text
        if annotate is True:
            annotate = "auto"
        elif annotate is False:
            annotate = None
        if annotate is not None and annotate != "auto":
            from ..core._ticks import validate_tick_format  # noqa: PLC0415

            validate_tick_format(annotate, who="Heatmap(annotate=)")
        self.data = as_data_ref(data)
        self.x, self.y, self.z = x, y, z
        self.colormap = colormap
        self.aggregator = aggregator
        self.annotate = annotate
        self._validate_tabular()
        self._freeze()

    def resolved_cell_labels(self, xs, ys, grid, theme):
        """The core-computed labels ([D113]) for an already-pivoted grid, or
        `[]` when the option is off — one call site per backend renderer."""
        if self.annotate is None:
            return []
        from ..core.encoding import heatmap_cell_labels  # noqa: PLC0415

        return heatmap_cell_labels(
            xs, ys, grid, spec=self.annotate, norm=self.norm_kind,
            vmin=self.vmin, vmax=self.vmax, gamma=self.gamma,
            linthresh=self.linthresh, levels=self.norm_levels,
            colormap=self.colormap,
            foreground=theme.foreground, background=theme.background)
