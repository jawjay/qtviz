"""Shape annotations — Rect / Ellipse / Polygon (roadmap wave 1).

Data-space outlines (fill opt-in) in the annotation class: literal
coordinates, no `DataRef`, theme-foreground default, composable via `*`.
Shapes are *data-space*: under a log scale their points transform like every
annotation, so an `Ellipse` stops looking elliptical there on every backend —
consistent by design.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..core._validate import check_alpha, check_color
from ..core.color import ColorSpec
from ..errors import ValidationError
from .annotations import _Reference


class _Shape(_Reference):
    """Shared shape surface: outline color/width, opt-in fill, alpha, label."""

    RECOMMENDED_OPTIONS = ("color", "line_width", "alpha", "fill", "label")
    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def _outline_points(self):
        raise NotImplementedError

    def lower(self, ctx):
        """One closed outline from the shared geometry."""
        import numpy as np  # noqa: PLC0415

        from ..core.lowering import Lowered, resolve_ref_color  # noqa: PLC0415
        from ..core.marks import Fill, PolygonMark, Stroke  # noqa: PLC0415

        pts = np.asarray(self._outline_points(), dtype="float64")
        color = resolve_ref_color(self.color, ctx.theme)
        mark = PolygonMark(
            pts[:, 0], pts[:, 1],
            stroke=Stroke(color, width=self.line_width, alpha=self.alpha),
            fill=Fill(color, self.alpha) if self.fill else None)
        return Lowered(marks=(mark,),
                       legend=self.legend_entry(ctx.theme, ctx.series_index))

    def _init_style(self, color, line_width, alpha, fill, label, who: str) -> None:
        check_alpha(alpha, who=who)
        check_color(color, who=who)
        self.color = color
        self.line_width = float(line_width)
        self.alpha = float(alpha)
        self.fill = bool(fill)
        self.label = label


class Rect(_Shape):
    """An axis-aligned rectangle from `(x0, y0)` to `(x1, y1)`."""

    REQUIRED_OPTIONS = ("x0", "y0", "x1", "y1")

    def __init__(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        fill: bool = False,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if not (float(x0) < float(x1) and float(y0) < float(y1)):
            raise ValidationError(
                f"Rect requires x0 < x1 and y0 < y1, got ({x0!r}, {y0!r}, {x1!r}, {y1!r})"
            )
        self.x0, self.y0 = float(x0), float(y0)
        self.x1, self.y1 = float(x1), float(y1)
        self._init_style(color, line_width, alpha, fill, label, "Rect")
        self._freeze()

    def _outline_points(self):
        from ..core._geometry import rect_points  # noqa: PLC0415

        return rect_points(self.x0, self.y0, self.x1, self.y1)


class Ellipse(_Shape):
    """An ellipse centered at `(cx, cy)` with radii `rx`/`ry`, rotated by
    `angle` degrees (counter-clockwise, about the center)."""

    REQUIRED_OPTIONS = ("cx", "cy", "rx", "ry")

    def __init__(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        *,
        angle: float = 0.0,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        fill: bool = False,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if not (float(rx) > 0 and float(ry) > 0):
            raise ValidationError(f"Ellipse radii must be positive, got ({rx!r}, {ry!r})")
        self.cx, self.cy = float(cx), float(cy)
        self.rx, self.ry = float(rx), float(ry)
        self.angle = float(angle)
        self._init_style(color, line_width, alpha, fill, label, "Ellipse")
        self._freeze()

    def _outline_points(self):
        from ..core._geometry import ellipse_points  # noqa: PLC0415

        return ellipse_points(self.cx, self.cy, self.rx, self.ry, self.angle)


class Polygon(_Shape):
    """A closed polygon through literal `points` (≥ 3 `(x, y)` pairs)."""

    REQUIRED_OPTIONS = ("points",)

    def __init__(
        self,
        points: Sequence[tuple[float, float]],
        *,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        fill: bool = False,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        pts = tuple((float(x), float(y)) for x, y in points)
        if len(pts) < 3:
            raise ValidationError(f"Polygon needs at least 3 points, got {len(pts)}")
        self.points = pts
        self._init_style(color, line_width, alpha, fill, label, "Polygon")
        self._freeze()

    def _outline_points(self):
        from ..core._geometry import close_points  # noqa: PLC0415

        return close_points(self.points)
