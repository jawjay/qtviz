"""Heatmap element — tabular x/y/z pivoted to a grid (spec §5.5)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element
from ..data import Accessor, as_data_ref


class Heatmap(Element):
    """A grid of tidy x/y cells shaded by a `z` value."""

    REQUIRED_OPTIONS = ("x", "y", "z")
    RECOMMENDED_OPTIONS = ("colormap", "aggregator")
    CHANNELS = ("x", "y", "z")

    def __init__(
        self,
        data,
        *,
        x: Accessor,
        y: Accessor,
        z: Accessor,
        colormap: str = "viridis",
        aggregator: Literal["mean", "sum", "count", "max", "min"] = "mean",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.x, self.y, self.z = x, y, z
        self.colormap = colormap
        self.aggregator = aggregator
        self._validate_tabular()
        self._freeze()
