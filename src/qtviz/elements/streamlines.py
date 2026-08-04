"""Streamlines element — field-line flow ([D118], wave 1.5)."""

from __future__ import annotations

import numpy as np

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..errors import ValidationError


class Streamlines(Element):
    """Streamlines of a vector field: `u`/`v` are 2-D arrays on the
    `Image`/`Contour` grid contract, placed in data space by `extent` —
    deliberately grids, not per-point columns, because field topology needs
    the grid. The integrator runs once in core (`_streamlines`): seeds on a
    coarse mask grid (`30×30 · density`), RK4 both directions with bilinear
    interpolation, termination on domain exit / stagnation / an occupied
    mask cell — the mask enforces line spacing. Every backend draws the
    resulting polylines + one mid-line [D107] arrowhead each as two cheap
    NaN-separated curves.

    Recorded v1 scope cuts: no `color_by=speed` gradient lines (pg cannot
    draw gradient polylines — the same honesty tier as `Curve(color_by=)`;
    revisit together), no varying line width, no start-point control."""

    # [D124]: holds raw 2-D arrays, no DataRef today; becomes "gridded"
    # when [D129] makes it data-first (wave 3).
    DATA_KIND = "none"
    REQUIRED_OPTIONS = ("extent",)
    RECOMMENDED_OPTIONS = ("density", "color", "line_width", "alpha", "label")

    def __init__(
        self,
        u,
        v,
        *,
        extent: tuple[float, float, float, float],
        density: float = 1.0,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Streamlines")
        u = np.asarray(u, dtype="float64")
        v = np.asarray(v, dtype="float64")
        if u.ndim != 2 or v.ndim != 2:
            raise ValidationError("Streamlines u/v must be 2-D arrays on the "
                                  "Image/Contour grid contract")
        if u.shape != v.shape:
            raise ValidationError(
                f"Streamlines u/v shapes must match, got {u.shape} vs {v.shape}")
        if not 0.0 < float(density) <= 5.0:
            raise ValidationError(
                f"Streamlines density must be in (0, 5], got {density!r}")
        self.u = u
        self.v = v
        self.extent = tuple(float(b) for b in extent)
        self.density = float(density)
        self.color = color
        self.line_width = float(line_width)
        self.alpha = alpha
        self.label = label
        self._freeze()

    def resolved_paths(self):
        """The shared core integration ([D110]): `(paths, heads)` polylines."""
        from ..core._streamlines import streamline_paths  # noqa: PLC0415

        return streamline_paths(self.u, self.v, self.extent, self.density)

    def resolved_segments(self):
        """The two NaN-separated polylines every backend draws — all lines
        joined, then all arrowheads joined: `((lx, ly), (hx, hy))`."""
        paths, heads = self.resolved_paths()
        return _nan_join(paths), _nan_join(heads)


def _nan_join(parts) -> tuple[np.ndarray, np.ndarray]:
    if not parts:
        empty = np.empty(0)
        return empty, empty.copy()
    gap = np.array([[np.nan, np.nan]])
    joined = np.vstack([q for p in parts for q in (p, gap)])[:-1]
    return joined[:, 0], joined[:, 1]
