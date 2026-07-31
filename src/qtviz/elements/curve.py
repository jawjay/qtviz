"""Curve element (spec §5.2)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError

# Step semantics ([D84]): where y[i] holds relative to x[i].
#   "post": y[i] holds on [x[i], x[i+1])   "pre": y[i] holds on (x[i-1], x[i]]
#   "mid":  the step lands at the midpoint between consecutive x.
_STEPS = ("pre", "mid", "post")
_MARKERS = ("circle", "square", "triangle", "diamond", "cross")


def check_axis(axis: str, scale: str, *, who: str) -> None:
    """Twin-axis field guard ([D88]): `axis` names a known y axis, and a
    datashaded element can't ride y2 (the raster pipeline is primary-axes)."""
    if axis not in ("y", "y2"):
        raise ValidationError(f"{who} axis must be 'y' or 'y2', got {axis!r}")
    if axis == "y2" and scale == "datashader":
        raise ValidationError(f"{who}: axis='y2' is not supported with scale='datashader'")


class Curve(Element):
    """A connected line through ordered x/y points; optionally stepped
    (`step=`) and/or with point markers (`marker=`) ([D84]); `axis="y2"`
    puts it on the twin right-hand axis ([D88])."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "marker", "step",
                           "alpha", "label", "axis")
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        line_style: Literal["solid", "dashed", "dotted", "dashdot"] = "solid",
        marker: Literal["circle", "square", "triangle", "diamond", "cross"] | None = None,
        step: Literal["pre", "mid", "post"] | None = None,
        alpha: float = 1.0,
        label: str | None = None,
        axis: Literal["y", "y2"] = "y",
        scale: Literal["native", "auto", "datashader"] = "native",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Curve")
        if step is not None and step not in _STEPS:
            raise ValidationError(f"Curve step must be one of {_STEPS} or None, got {step!r}")
        if marker is not None and marker not in _MARKERS:
            raise ValidationError(
                f"Curve marker must be one of {_MARKERS} or None, got {marker!r}"
            )
        check_axis(axis, scale, who="Curve")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.marker = marker
        self.step = step
        self.alpha = alpha
        self.label = label
        self.axis = axis
        self.scale = scale
        self._validate_tabular()
        self._freeze()
