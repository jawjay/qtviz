"""Image element (spec §5.4)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element, require_gridded
from ..core.encoding import Norm
from ..data import DataLike, as_data_ref
from ..errors import ValidationError
from ._norm import NormedRaster, check_norm_clim


class Image(NormedRaster, Element):
    """A 2-D array drawn as an image over explicit `extent` (also hosts RGBA
    rasters). `norm`/`vmin`/`vmax`/`gamma` engage the [D105] color surface —
    normalized once in core, colorbar/limits appear only when used."""

    DATA_KIND = "gridded"  # [D124]
    REQUIRED_OPTIONS = ("extent",)
    RECOMMENDED_OPTIONS = ("colormap", "interpolation", "norm", "clim", "alpha")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "clim", "colormap", "interpolation", "norm"})

    def __init__(
        self,
        data: DataLike,
        *,
        extent: tuple[float, float, float, float],
        colormap: str = "viridis",
        interpolation: Literal["nearest", "bilinear"] = "bilinear",
        norm: str | Norm = "linear",
        clim: tuple[float | None, float | None] | None = None,
        alpha: float = 1.0,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from ..core._validate import check_alpha  # noqa: PLC0415

        check_alpha(alpha, who="Image")
        self.norm, self.clim = check_norm_clim(norm, clim, who="Image")
        self.alpha = float(alpha)
        self.data = as_data_ref(data)
        if len(tuple(extent)) != 4:
            raise ValidationError(
                f"Image extent must be (xmin, xmax, ymin, ymax), got {extent!r}"
            )
        self.extent = tuple(float(b) for b in extent)
        self.colormap = colormap
        self.interpolation = interpolation
        require_gridded(self.data, who="Image")
        shape = self.data.schema().shape
        if shape is not None and not (
            len(shape) == 2 or (len(shape) == 3 and shape[-1] in (3, 4))
        ):
            raise ValidationError(
                f"Image data must be a 2-D array (or H×W×3/4 RGB(A)), got shape {shape}"
            )
        self._freeze()

    def resolved_grid(self):
        """[D124] the one gridded accessor: the resolved `GridData` — replaces
        scattered `element.data.grid()` reach-through in the backends."""
        return self.data.grid()
