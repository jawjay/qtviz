"""Mesh element — non-uniform rectilinear grids ([D106], the pcolormesh
analog; roadmap wave 3)."""

from __future__ import annotations

import numpy as np

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref
from ..errors import ValidationError
from .image import check_norm


def _check_edges(name: str, edges) -> tuple[float, ...]:
    """[D111]: edges are 1-D and strictly increasing, with the rectilinear
    boundary named explicitly instead of a raw numpy error."""
    try:
        arr = np.asarray(edges, dtype="float64")
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Mesh {name} must be numeric: {e}") from e
    if arr.ndim != 1:
        raise ValidationError(
            f"Mesh {name} must be 1-D (rectilinear); curvilinear meshes are not "
            "supported — see design/roadmap-post-rerun.md §6"
        )
    if arr.size < 2 or np.any(np.diff(arr) <= 0):
        raise ValidationError(f"Mesh {name} must be ≥2 strictly increasing values")
    return tuple(float(v) for v in arr)


class Mesh(Element):
    """A 2-D value grid over **explicit cell edges**: `values[j, i]` fills the
    cell `x[i]..x[i+1] × y[j]..y[j+1]` — edges are the
    canonical contract (`Heatmap` owns the centers convention; `Image` the
    uniform-bounds one). Non-uniform spacing is the point: log-spaced
    frequency rows, irregular time bins. Shares the [D105] norm surface."""

    DATA_KIND = "gridded"  # [D124]
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("colormap", "norm", "vmin", "vmax", "gamma",
                           "linthresh", "levels")

    def __init__(
        self,
        data: DataLike,
        *,
        x,
        y,
        colormap: str = "viridis",
        norm: str = "linear",
        vmin: float | None = None,
        vmax: float | None = None,
        gamma: float = 1.0,
        linthresh: float = 1.0,
        levels: tuple[float, ...] | list[float] | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_norm(norm, vmin, vmax, gamma, who="Mesh",
                   linthresh=linthresh, levels=levels)
        xe = _check_edges("x", x)
        ye = _check_edges("y", y)
        self.data = as_data_ref(data)
        self.x, self.y = xe, ye
        self.colormap = colormap
        self.norm = norm
        self.vmin = float(vmin) if vmin is not None else None
        self.vmax = float(vmax) if vmax is not None else None
        self.gamma = float(gamma)
        self.linthresh = float(linthresh)
        self.levels = tuple(float(v) for v in levels) if levels is not None else None
        require_gridded(self.data, who="Mesh")
        shape = self.data.schema().shape
        if shape is not None and len(shape) == 2:  # lazy refs without a shape defer
            nrows, ncols = shape
            if len(xe) != ncols + 1:
                raise ValidationError(
                    f"Mesh x has {len(xe)} values for {ncols} value columns "
                    f"(want ncols+1 = {ncols + 1})"
                )
            if len(ye) != nrows + 1:
                raise ValidationError(
                    f"Mesh y has {len(ye)} values for {nrows} value rows "
                    f"(want nrows+1 = {nrows + 1})"
                )
        self._freeze()

    def check_shape(self, values) -> np.ndarray:
        """Render-seam guard: `(len(y)-1, len(x)-1)` values."""
        a = np.asarray(values, dtype="float64")
        want = (len(self.y) - 1, len(self.x) - 1)
        if a.shape != want:
            raise ValidationError(
                f"Mesh values shape {a.shape} does not match edges (want {want})"
            )
        return a
