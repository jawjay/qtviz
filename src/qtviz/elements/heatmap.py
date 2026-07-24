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
    was `"last"`, kept in the vocabulary)."""

    REQUIRED_OPTIONS = ("x", "y", "z")
    RECOMMENDED_OPTIONS = ("colormap", "aggregator")
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
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if aggregator not in GRID_AGGS:
            raise ValidationError(
                f"aggregator must be one of {GRID_AGGS}, got {aggregator!r}"
            )
        self.data = as_data_ref(data)
        self.x, self.y, self.z = x, y, z
        self.colormap = colormap
        self.aggregator = aggregator
        self._validate_tabular()
        self._freeze()
