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
    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

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

    def select_xy(self):
        """Brush registration ([D124]) — heads select like Scatter points."""
        return self.data.series("x"), self.data.series("y")

    def lower(self, ctx):
        """[D122]: ONE pair-connected polyline for every stalk ([D115] — never
        an item per stem) + a pickable marker layer for the heads."""
        from ..core._time import as_float_seconds  # noqa: PLC0415
        from ..core.lowering import Lowered, resolve_color  # noqa: PLC0415
        from ..core.marks import Markers, Polyline, Stroke  # noqa: PLC0415

        sx, sy = self.resolved_segments()
        color = resolve_color(self.color, ctx.theme, ctx.series_index)
        d = self.data
        marks = (
            Polyline(sx, sy, Stroke(color, width=self.line_width, alpha=self.alpha),
                     connect="pairs"),
            Markers(as_float_seconds(d.series("x")), as_float_seconds(d.series("y")),
                    marker=self.marker, size=7.0,
                    fill=color, alpha=self.alpha, pickable=True),
        )
        return Lowered(marks=marks,
                       legend=self.legend_entry(ctx.theme, ctx.series_index),
                       select_xy=self.select_xy())
