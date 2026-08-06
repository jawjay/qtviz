"""Scatter element (spec §5.1)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_agg, check_alpha, check_choice, check_color, check_exclusive
from ..core.color import ColorSpec
from ..core.element import Element, ElementId
from ..core.encoding import Norm
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError
from ._norm import NormedRaster, check_norm_clim


class Scatter(NormedRaster, Element):
    """A point cloud — x/y positions with optional `color`/`size` encoding.
    `norm`/`clim` engage the shared colormap-normalization surface on the
    `color_by` mapping — the same vocabulary Image/Heatmap/Mesh use."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "color_by", "size", "size_by", "alpha", "marker",
                           "norm", "clim", "label", "axis")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "axis", "clim", "color", "color_by", "label",
                                "marker", "norm", "size", "size_by"})
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        color: ColorSpec | None = None,
        color_by: Accessor | None = None,
        size: float | None = None,
        size_by: Accessor | None = None,
        marker: Literal["circle", "square", "triangle", "triangle_down", "diamond",
                        "cross", "plus", "star", "pentagon", "hexagon"] = "circle",
        alpha: float = 1.0,
        norm: str | Norm = "linear",
        clim: tuple[float | None, float | None] | None = None,
        label: str | None = None,
        axis: Literal["y", "y2"] = "y",
        raster: Literal["native", "auto", "datashader"] = "native",
        agg: Literal["auto", "count", "sum", "mean", "max", "min", "std", "any", "by"] = "auto",
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from .curve import _MARKERS, check_axis  # noqa: PLC0415 — shared [D88] guard + marker set

        check_exclusive(color, color_by, names=("color", "color_by"), who="Scatter")
        check_exclusive(size, size_by, names=("size", "size_by"), who="Scatter")
        check_color(color, who="Scatter")
        check_alpha(alpha, who="Scatter")
        check_choice(marker, _MARKERS, who="Scatter", param="marker")
        check_agg(agg, color_by, raster, who="Scatter")
        check_axis(axis, raster, who="Scatter")
        self.norm, self.clim = check_norm_clim(norm, clim, who="Scatter")
        if color_by is None and (self.norm_kind != "linear" or self.clim is not None):
            raise ValidationError(
                "Scatter norm/clim require color_by (they norm the mapped column)")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color, self.color_by = color, color_by
        self.size, self.size_by = size, size_by
        self.marker, self.alpha = marker, alpha
        self.label = label
        self.axis = axis
        self.raster = raster
        self.agg = agg
        self._validate_tabular()
        self._freeze()

    def legend_entry(self, theme, index: int = 0):
        """A `color_by` Scatter already emits its own categorical/continuous
        `Legend` from the color mapping — contributing a swatch entry too would
        double-legend ([D60] risk #3), so it opts out of the contract."""
        if self.color_by is not None:
            return None
        return super().legend_entry(theme, index)

    def select_xy(self):
        """Brush/pick registration coordinates — replaces the
        isinstance tuples in backend event wiring."""
        return self.data.series("x"), self.data.series("y")

    def channels(self) -> dict:
        """x/y always; `color`/`size` roles when bound to a data column, so the
        resolve pipeline materializes them for the native renderers."""
        ch = {"x": self.x, "y": self.y}
        if self.color_by is not None:
            ch["color"] = self.color_by
        if self.size_by is not None:
            ch["size"] = self.size_by
        return ch
