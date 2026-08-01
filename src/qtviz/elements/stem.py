"""Stem element — lollipop/stem plots ([D115], wave 1.4)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Stem(Element):
    """A stem (lollipop) series: a vertical line from `baseline` to each
    `(x, y)`, capped by a marker head. The segment geometry is computed once
    in core (`_geometry.stem_segments`, [D110]) and drawn as ONE
    pair-connected polyline plus a marker layer per backend — never an item
    per stem. Heads pick/hover like Scatter points; the element takes a
    palette slot and contributes a legend entry like any series."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("baseline", "marker", "color", "line_width", "alpha",
                           "label")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        baseline: float = 0.0,
        marker: Literal["circle", "square", "triangle", "triangle_down", "diamond",
                        "cross", "plus", "star", "pentagon", "hexagon"] = "circle",
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Stem")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.baseline = float(baseline)
        self.marker = marker
        self.color = color
        self.line_width = float(line_width)
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()

    def resolved_segments(self):
        """The shared core stem geometry from the resolved channels ([D110])."""
        from ..core._geometry import stem_segments  # noqa: PLC0415
        from ..core._time import as_float_seconds  # noqa: PLC0415

        d = self.data
        return stem_segments(as_float_seconds(d.series("x")),
                             as_float_seconds(d.series("y")), self.baseline)
