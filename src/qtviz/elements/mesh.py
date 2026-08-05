"""Mesh element — non-uniform rectilinear grids (the pcolormesh
analog; roadmap wave 3)."""

from __future__ import annotations

import numpy as np

from ..core.element import Element, require_gridded
from ..core.encoding import Norm
from ..data import DataLike, as_data_ref
from ..errors import ValidationError
from ._norm import NormedRaster, check_norm_clim


def _check_edges(name: str, edges) -> tuple[float, ...]:
    """Edges are 1-D and strictly increasing, with the rectilinear
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


class Mesh(NormedRaster, Element):
    """A 2-D value grid over **explicit cell edges**: `values[j, i]` fills the
    cell `x[i]..x[i+1] × y[j]..y[j+1]` — edges are the
    canonical contract (`Heatmap` owns the centers convention; `Image` the
    uniform-bounds one). Non-uniform spacing is the point: log-spaced
    frequency rows, irregular time bins. Shares the norm surface."""

    DATA_KIND = "gridded"  # [D124]
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("colormap", "norm", "clim", "alpha")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "clim", "colormap", "norm"})

    def __init__(
        self,
        data: DataLike,
        *,
        x,
        y,
        colormap: str = "viridis",
        norm: str | Norm = "linear",
        clim: tuple[float | None, float | None] | None = None,
        alpha: float = 1.0,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from ..core._validate import check_alpha  # noqa: PLC0415

        check_alpha(alpha, who="Mesh")
        self.norm, self.clim = check_norm_clim(norm, clim, who="Mesh")
        self.alpha = float(alpha)
        xe = _check_edges("x", x)
        ye = _check_edges("y", y)
        self.data = as_data_ref(data)
        self.x, self.y = xe, ye
        self.colormap = colormap
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

    def resolved_grid(self):
        """The one gridded accessor: the resolved `GridData` — replaces
        scattered `element.data.grid()` reach-through in the backends."""
        return self.data.grid()

    def check_shape(self, values) -> np.ndarray:
        """Render-seam guard: `(len(y)-1, len(x)-1)` values."""
        a = np.asarray(values, dtype="float64")
        want = (len(self.y) - 1, len(self.x) - 1)
        if a.shape != want:
            raise ValidationError(
                f"Mesh values shape {a.shape} does not match edges (want {want})"
            )
        return a
