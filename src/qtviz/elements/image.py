"""Image element (spec §5.4)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref


class Image(Element):
    """A 2-D array drawn as an image over explicit `bounds` (also hosts RGBA rasters)."""

    REQUIRED_OPTIONS = ("bounds",)
    RECOMMENDED_OPTIONS = ("colormap", "interpolation")

    def __init__(
        self,
        data: DataLike,
        *,
        bounds: tuple[float, float, float, float],
        colormap: str = "viridis",
        interpolation: Literal["nearest", "bilinear"] = "bilinear",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.bounds = tuple(float(b) for b in bounds)
        self.colormap = colormap
        self.interpolation = interpolation
        require_gridded(self.data, who="Image")
        self._freeze()
