"""Image element (spec §5.4)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element, require_gridded
from ..core.encoding import Norm
from ..data import DataLike, as_data_ref
from ._norm import NormedRaster, check_norm_clim


class Image(NormedRaster, Element):
    """A 2-D array drawn as an image over explicit `extent` (also hosts RGBA
    rasters). `norm`/`vmin`/`vmax`/`gamma` engage the [D105] color surface —
    normalized once in core, colorbar/limits appear only when used."""

    DATA_KIND = "gridded"  # [D124]
    REQUIRED_OPTIONS = ("extent",)
    RECOMMENDED_OPTIONS = ("colormap", "interpolation", "norm", "clim")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"clim", "colormap", "interpolation", "norm"})

    def __init__(
        self,
        data: DataLike,
        *,
        extent: tuple[float, float, float, float],
        colormap: str = "viridis",
        interpolation: Literal["nearest", "bilinear"] = "bilinear",
        norm: str | Norm = "linear",
        clim: tuple[float | None, float | None] | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.norm, self.clim = check_norm_clim(norm, clim, who="Image")
        self.data = as_data_ref(data)
        self.extent = tuple(float(b) for b in extent)
        self.colormap = colormap
        self.interpolation = interpolation
        require_gridded(self.data, who="Image")
        self._freeze()

    def resolved_grid(self):
        """[D124] the one gridded accessor: the resolved `GridData` — replaces
        scattered `element.resolved_grid()` reach-through in the backends."""
        return self.resolved_grid()
