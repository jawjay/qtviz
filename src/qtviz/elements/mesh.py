"""Mesh element — non-uniform rectilinear grids ([D106], the pcolormesh
analog; roadmap wave 3)."""

from __future__ import annotations

import numpy as np

from ..core.element import Element, require_gridded
from ..data import DataLike, as_data_ref
from ..errors import ValidationError
from .image import check_norm


class Mesh(Element):
    """A 2-D value grid over **explicit cell edges**: `values[j, i]` fills the
    cell `x_edges[i]..x_edges[i+1] × y_edges[j]..y_edges[j+1]` — edges are the
    canonical contract (`Heatmap` owns the centers convention; `Image` the
    uniform-bounds one). Non-uniform spacing is the point: log-spaced
    frequency rows, irregular time bins. Shares the [D105] norm surface."""

    REQUIRED_OPTIONS = ("x_edges", "y_edges")
    RECOMMENDED_OPTIONS = ("colormap", "norm", "vmin", "vmax", "gamma")

    def __init__(
        self,
        data: DataLike,
        *,
        x_edges,
        y_edges,
        colormap: str = "viridis",
        norm: str = "linear",
        vmin: float | None = None,
        vmax: float | None = None,
        gamma: float = 1.0,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_norm(norm, vmin, vmax, gamma, who="Mesh")
        xe = tuple(float(v) for v in x_edges)
        ye = tuple(float(v) for v in y_edges)
        for name, edges in (("x_edges", xe), ("y_edges", ye)):
            if len(edges) < 2 or any(b <= a for a, b in zip(edges, edges[1:], strict=False)):
                raise ValidationError(
                    f"Mesh {name} must be ≥2 strictly increasing values"
                )
        self.data = as_data_ref(data)
        self.x_edges, self.y_edges = xe, ye
        self.colormap = colormap
        self.norm = norm
        self.vmin = float(vmin) if vmin is not None else None
        self.vmax = float(vmax) if vmax is not None else None
        self.gamma = float(gamma)
        require_gridded(self.data, who="Mesh")
        self._freeze()

    def check_shape(self, values) -> np.ndarray:
        """Render-seam guard: `(len(y_edges)-1, len(x_edges)-1)` values."""
        a = np.asarray(values, dtype="float64")
        want = (len(self.y_edges) - 1, len(self.x_edges) - 1)
        if a.shape != want:
            raise ValidationError(
                f"Mesh values shape {a.shape} does not match edges (want {want})"
            )
        return a
