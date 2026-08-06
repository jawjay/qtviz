"""Curve element (spec §5.2)."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha, check_choice, check_color
from ..core.color import ColorSpec
from ..core.element import Element, ElementId
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError

# Step semantics ([D84]): where y[i] holds relative to x[i].
#   "post": y[i] holds on [x[i], x[i+1])   "pre": y[i] holds on (x[i-1], x[i]]
#   "mid":  the step lands at the midpoint between consecutive x.
_STEPS = ("pre", "mid", "post")
_MARKERS = ("circle", "square", "triangle", "triangle_down", "diamond", "cross",
            "plus", "star", "pentagon", "hexagon")
_NAMED_STYLES = ("solid", "dashed", "dotted", "dashdot")


def check_line_style(style, *, who: str) -> None:
    """`line_style` is a named style or an on/off dash-length tuple in
    points — validated at construction, translated per backend."""
    if isinstance(style, str):
        if style not in _NAMED_STYLES:
            raise ValidationError(
                f"{who} line_style must be one of {_NAMED_STYLES} or a dash tuple, "
                f"got {style!r}")
        return
    try:
        vals = tuple(float(v) for v in style)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{who} line_style must be a named style or a tuple of dash lengths, "
            f"got {style!r}") from None
    if len(vals) < 2 or len(vals) % 2 or any(v <= 0 for v in vals):
        raise ValidationError(
            f"{who} dash tuple needs an even number of positive lengths, got {style!r}")


def check_axis(axis: str, raster: str, *, who: str) -> None:
    """Twin-axis field guard: `axis` names a known y axis, and a
    datashaded element can't ride y2 (the raster pipeline is primary-axes)."""
    if axis not in ("y", "y2"):
        raise ValidationError(f"{who} axis must be 'y' or 'y2', got {axis!r}")
    if axis == "y2" and raster == "datashader":
        raise ValidationError(f"{who}: axis='y2' is not supported with raster='datashader'")


class Curve(Element):
    """A connected line through ordered x/y points; optionally stepped
    (`step=`) and/or with point markers (`marker=`); `axis="y2"`
    puts it on the twin right-hand axis."""

    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "color_by", "line_width", "line_style", "marker",
                           "marker_every", "step", "alpha", "label", "axis")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "axis", "color", "color_by", "label", "line_style",
                                "line_width", "marker", "marker_every", "step"})
    CHANNELS = ("x", "y")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        color: ColorSpec | None = None,
        color_by: Accessor | None = None,
        line_width: float = 1.5,
        line_style: str | tuple[float, ...] = "solid",
        marker: str | None = None,
        marker_every: int = 1,
        step: Literal["pre", "mid", "post"] | None = None,
        alpha: float = 1.0,
        label: str | None = None,
        axis: Literal["y", "y2"] = "y",
        raster: Literal["native", "auto", "datashader"] = "native",
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Curve")
        check_color(color, who="Curve")
        check_line_style(line_style, who="Curve")
        from ..core._validate import check_exclusive  # noqa: PLC0415

        check_exclusive(color, color_by, names=("color", "color_by"), who="Curve")
        if color_by is not None and (marker is not None or step is not None
                                     or raster == "datashader"):
            raise ValidationError(
                "Curve color_by is a plain-line encoding (no marker/step/datashader) "
                "in this release"
            )
        check_choice(step, _STEPS, who="Curve", param="step", none_ok=True)
        check_choice(marker, _MARKERS, who="Curve", param="marker", none_ok=True)
        if not isinstance(marker_every, int) or isinstance(marker_every, bool) \
                or marker_every < 1:
            raise ValidationError(f"marker_every must be a positive int, got {marker_every!r}")
        check_axis(axis, raster, who="Curve")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.color = color
        self.color_by = color_by
        self.line_width = line_width
        self.line_style = line_style if isinstance(line_style, str) \
            else tuple(float(v) for v in line_style)
        self.marker = marker
        self.marker_every = marker_every
        self.step = step
        self.alpha = alpha
        self.label = label
        self.axis = axis
        self.raster = raster
        self._validate_tabular()
        self._freeze()

    def legend_entry(self, theme, index: int = 0):
        """A `color_by` Curve emits its own categorical/continuous key —
        contributing a swatch too would double-legend ([D60] risk #3)."""
        if self.color_by is not None:
            return None
        return super().legend_entry(theme, index)

    def select_xy(self):
        """Brush/pick registration coordinates — replaces the
        isinstance tuples in backend event wiring."""
        return self.data.series("x"), self.data.series("y")

    def channels(self) -> dict:
        ch = {"x": self.x, "y": self.y}
        if self.color_by is not None:
            ch["color"] = self.color_by
        return ch
