"""Shape annotations — Rect / Ellipse / Polygon ([D97], roadmap wave 1).

Data-space outlines (fill opt-in) in the [D70] annotation class: literal
coordinates, no `DataRef`, theme-foreground default, composable via `*`.
Shapes are *data-space*: under a log scale their points transform like every
annotation, so an `Ellipse` stops looking elliptical there on every backend —
consistent by design.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..errors import ValidationError
from .annotations import _Reference


class _Shape(_Reference):
    """Shared shape surface: outline color/width, opt-in fill, alpha, label."""

    RECOMMENDED_OPTIONS = ("color", "line_width", "alpha", "fill", "label")

    def _init_style(self, color, line_width, alpha, fill, label, who: str) -> None:
        check_alpha(alpha, who=who)
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
