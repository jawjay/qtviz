"""Image element (spec §5.4)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref


def check_norm(norm: str, vmin, vmax, gamma: float, *, who: str) -> None:
    """[D105] guard shared by the raster elements."""
    from ..core.encoding import RASTER_NORMS  # noqa: PLC0415
    from ..errors import ValidationError  # noqa: PLC0415

    if norm not in RASTER_NORMS:
        raise ValidationError(f"{who} norm must be one of {RASTER_NORMS}, got {norm!r}")
    if gamma != 1.0 and norm != "power":
        raise ValidationError(f"{who}: gamma requires norm='power'")
    if gamma <= 0:
        raise ValidationError(f"{who}: gamma must be positive, got {gamma!r}")
    if vmin is not None and vmax is not None and not float(vmin) < float(vmax):
        raise ValidationError(f"{who}: vmin must be < vmax, got ({vmin!r}, {vmax!r})")
    if norm == "log" and vmin is not None and float(vmin) <= 0:
        raise ValidationError(f"{who}: norm='log' requires a positive vmin")


class Image(Element):
    """A 2-D array drawn as an image over explicit `bounds` (also hosts RGBA
    rasters). `norm`/`vmin`/`vmax`/`gamma` engage the [D105] color surface —
    normalized once in core, colorbar/limits appear only when used."""

    REQUIRED_OPTIONS = ("bounds",)
    RECOMMENDED_OPTIONS = ("colormap", "interpolation", "norm", "vmin", "vmax", "gamma")

    def __init__(
        self,
        data: DataLike,
        *,
        bounds: tuple[float, float, float, float],
        colormap: str = "viridis",
        interpolation: Literal["nearest", "bilinear"] = "bilinear",
        norm: Literal["linear", "log", "power"] = "linear",
        vmin: float | None = None,
        vmax: float | None = None,
        gamma: float = 1.0,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_norm(norm, vmin, vmax, gamma, who="Image")
        self.data = as_data_ref(data)
        self.bounds = tuple(float(b) for b in bounds)
        self.colormap = colormap
        self.interpolation = interpolation
        self.norm = norm
        self.vmin = float(vmin) if vmin is not None else None
        self.vmax = float(vmax) if vmax is not None else None
        self.gamma = float(gamma)
        require_gridded(self.data, who="Image")
        self._freeze()
