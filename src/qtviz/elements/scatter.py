"""Scatter element (spec §5.1)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_agg, check_alpha, check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Scatter(Element):
    """A point cloud — x/y positions with optional `color`/`size` encoding."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "color_by", "size", "size_by", "alpha", "marker",
                           "color_norm", "label", "axis")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        color: ColorSpec | None = None,
        color_by: str | None = None,
        size: float | None = None,
        size_by: str | None = None,
        marker: Literal["circle", "square", "triangle", "diamond", "cross"] = "circle",
        alpha: float = 1.0,
        color_norm: Literal["linear", "log"] = "linear",
        label: str | None = None,
        axis: Literal["y", "y2"] = "y",
        scale: Literal["native", "auto", "datashader"] = "native",
        agg: Literal["auto", "count", "sum", "mean", "max", "min", "std", "any", "by"] = "auto",
        backend_hint: str | None = None,
        id=None,
        pyqtgraph_use_opengl: bool = False,
        matplotlib_rasterized: bool = False,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_exclusive(color, color_by, names=("color", "color_by"), who="Scatter")
        check_exclusive(size, size_by, names=("size", "size_by"), who="Scatter")
        check_alpha(alpha, who="Scatter")
        check_agg(agg, color_by, scale, who="Scatter")
        check_axis(axis, scale, who="Scatter")
        if pyqtgraph_use_opengl:
            import warnings  # noqa: PLC0415

            warnings.warn(
                "Scatter(pyqtgraph_use_opengl=...) was never wired and is deprecated "
                "(owner ruling, 2026-07-31); removal follows the >=2-minor warning "
                "policy (docs/stability.md). "
                "pyqtgraph's default raster path already handles large scatters, and "
                "huge data routes through scale='datashader'.",
                DeprecationWarning,
                stacklevel=2,
            )
        if color_norm not in ("linear", "log"):
            raise ValidationError(f"color_norm must be 'linear' or 'log', got {color_norm!r}")
        if color_norm != "linear" and color_by is None:
            raise ValidationError("color_norm requires color_by (it norms the mapped column)")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color, self.color_by = color, color_by
        self.size, self.size_by = size, size_by
        self.marker, self.alpha = marker, alpha
        self.color_norm = color_norm
        self.label = label
        self.axis = axis
        self.scale = scale
        self.agg = agg
        self.pyqtgraph_use_opengl = pyqtgraph_use_opengl
        self.matplotlib_rasterized = matplotlib_rasterized
        self._validate_tabular()
        self._freeze()

    def legend_entry(self, theme, index: int = 0):
        """A `color_by` Scatter already emits its own categorical/continuous
        `Legend` from the color mapping — contributing a swatch entry too would
        double-legend ([D60] risk #3), so it opts out of the contract."""
        if self.color_by is not None:
            return None
        return super().legend_entry(theme, index)

    def channels(self) -> dict:
        """x/y always; `color`/`size` roles when bound to a data column, so the
        resolve pipeline materializes them for the native renderers."""
        ch = {"x": self.x, "y": self.y}
        if self.color_by is not None:
            ch["color"] = self.color_by
        if self.size_by is not None:
            ch["size"] = self.size_by
        return ch
