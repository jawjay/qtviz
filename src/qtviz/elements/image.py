"""Image element (spec §5.4)."""

from __future__ import annotations

from typing import Literal

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref


def check_norm(norm: str, vmin, vmax, gamma: float, *, who: str,
               linthresh: float = 1.0, levels=None) -> None:
    """[D105] guard shared by the raster elements ([D114] adds the
    symlog/boundary tail)."""
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
    if float(linthresh) <= 0:
        raise ValidationError(f"{who}: linthresh must be positive, got {linthresh!r}")
    if float(linthresh) != 1.0 and norm != "symlog":
        raise ValidationError(f"{who}: linthresh requires norm='symlog'")
    if norm == "boundary":
        if levels is None:
            raise ValidationError(f"{who}: norm='boundary' requires levels=")
        lv = [float(v) for v in levels]
        if len(lv) < 2 or any(b <= a for a, b in zip(lv, lv[1:], strict=False)):
            raise ValidationError(
                f"{who}: boundary levels must be ≥2 ascending values, got {levels!r}")
    elif levels is not None:
        raise ValidationError(f"{who}: levels requires norm='boundary'")


class Image(Element):
    """A 2-D array drawn as an image over explicit `extent` (also hosts RGBA
    rasters). `norm`/`vmin`/`vmax`/`gamma` engage the [D105] color surface —
    normalized once in core, colorbar/limits appear only when used."""

    DATA_KIND = "gridded"  # [D124]
    REQUIRED_OPTIONS = ("extent",)
    RECOMMENDED_OPTIONS = ("colormap", "interpolation", "norm", "vmin", "vmax", "gamma",
                           "linthresh", "levels")

    def __init__(
        self,
        data: DataLike,
        *,
        extent: tuple[float, float, float, float],
        colormap: str = "viridis",
        interpolation: Literal["nearest", "bilinear"] = "bilinear",
        norm: Literal["linear", "log", "power", "symlog", "boundary"] = "linear",
        vmin: float | None = None,
        vmax: float | None = None,
        gamma: float = 1.0,
        linthresh: float = 1.0,
        levels: tuple[float, ...] | list[float] | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_norm(norm, vmin, vmax, gamma, who="Image",
                   linthresh=linthresh, levels=levels)
        self.data = as_data_ref(data)
        self.extent = tuple(float(b) for b in extent)
        self.colormap = colormap
        self.interpolation = interpolation
        self.norm = norm
        self.vmin = float(vmin) if vmin is not None else None
        self.vmax = float(vmax) if vmax is not None else None
        self.gamma = float(gamma)
        self.linthresh = float(linthresh)
        self.levels = tuple(float(v) for v in levels) if levels is not None else None
        require_gridded(self.data, who="Image")
        self._freeze()
