"""Heatmap element — tabular x/y/z pivoted to a grid (spec §5.5)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element, require_tabular_columns
from ..data import as_data_ref


class Heatmap(Element):
    REQUIRED_OPTIONS = ("x", "y", "z")
    RECOMMENDED_OPTIONS = ("colormap", "aggregator")

    def __init__(
        self,
        data,
        *,
        x: str,
        y: str,
        z: str,
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
        require_tabular_columns(self.data, [x, y, z], who="Heatmap")
        self._freeze()
