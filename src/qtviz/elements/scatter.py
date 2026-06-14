"""Scatter element (spec §5.1)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, as_data_ref


class Scatter(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "color_by", "size", "size_by", "alpha", "marker")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data,
        *,
        x: Accessor,
        y: Accessor,
        color: ColorSpec | None = None,
        color_by: str | None = None,
        size: float | None = None,
        size_by: str | None = None,
        marker: Literal["circle", "square", "triangle", "diamond", "cross"] = "circle",
        alpha: float = 1.0,
        scale: Literal["native", "auto", "datashader"] = "native",
        backend_hint: str | None = None,
        id=None,
        pyqtgraph_use_opengl: bool = False,
        matplotlib_rasterized: bool = False,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if color is not None and color_by is not None:
            raise ValueError("Scatter: pass color (static) or color_by (column), not both")
        if size is not None and size_by is not None:
            raise ValueError("Scatter: pass size (static) or size_by (column), not both")
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color, self.color_by = color, color_by
        self.size, self.size_by = size, size_by
        self.marker, self.alpha = marker, alpha
        self.scale = scale
        self.pyqtgraph_use_opengl = pyqtgraph_use_opengl
        self.matplotlib_rasterized = matplotlib_rasterized
        self._validate_tabular()
        self._freeze()
