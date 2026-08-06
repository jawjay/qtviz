"""Polar plotting ([D119] Option B — `design/spikes/polar-spike-report.md`).

Polar is a **transform, not a projection**: `polar()` rebinds a tabular
element's x/y through `(θ, r) → (r·cosθ, r·sinθ)` before the data seam,
`PolarGrid` draws the circular chrome (rings/spokes/labels) from marks —
one `lower()`, zero backend edits — and `wedge()` builds annulus-sector
points for `Polygon` polar bars. The surface stays rectilinear (pair with
`.opts(aspect=1, grid=False)` and `AxisSpec(ticks=())`), so R1, events,
brushes, `ViewState`, and backend switching are untouched by design.
The recorded costs of that choice (hover reads x/y, no r-zoom semantics)
live in the spike report.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..core.element import Element, ElementId
from ..data import Accessor
from ..data.expr import Expr, col
from ..errors import ValidationError


class PolarGrid(Element):
    """Circular grid chrome ([D70]-class): `rings` concentric circles out to
    `r_max`, `spokes` radial lines, degree labels (or custom `theta_labels` —
    the radar case) and radius labels. Chrome, not data: it binds nothing,
    draws in the theme foreground, and contributes no legend entry."""

    DATA_KIND = "none"
    REQUIRED_OPTIONS = ("r_max",)
    RECOMMENDED_OPTIONS = ("rings", "spokes", "theta_labels", "r_labels",
                           "color", "alpha")
    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def __init__(self, r_max: float, *, rings: int = 4, spokes: int = 8,
                 theta_labels: bool | Sequence[str] = True,
                 r_labels: bool = True, color=None, alpha: float = 0.35,
                 backend_hint: str | None = None,
                 id: ElementId | None = None) -> None:
        from ..core._validate import check_alpha, check_color  # noqa: PLC0415

        super().__init__(backend_hint=backend_hint, id=id)
        if not float(r_max) > 0.0:
            raise ValidationError(f"PolarGrid r_max must be > 0, got {r_max!r}")
        if int(rings) < 1:
            raise ValidationError(f"PolarGrid rings must be >= 1, got {rings!r}")
        if int(spokes) < 2:
            raise ValidationError(f"PolarGrid spokes must be >= 2, got {spokes!r}")
        if not isinstance(theta_labels, bool):
            theta_labels = tuple(str(s) for s in theta_labels)
            if len(theta_labels) != int(spokes):
                raise ValidationError(
                    f"PolarGrid theta_labels needs one label per spoke "
                    f"({spokes}), got {len(theta_labels)}")
        check_color(color, who="PolarGrid")
        check_alpha(alpha, who="PolarGrid")
        self.r_max = float(r_max)
        self.rings = int(rings)
        self.spokes = int(spokes)
        self.theta_labels = theta_labels
        self.r_labels = bool(r_labels)
        self.color = color
        self.alpha = float(alpha)
        self._freeze()

    def legend_entry(self, theme, index: int = 0):
        return None  # chrome never claims a legend slot

    def lower(self, ctx):
        """Rings as ONE NaN-separated `PolygonMark`, spokes as ONE
        pair-connected `Polyline`, labels as `TextMark`s."""
        from ..core._geometry import ellipse_points  # noqa: PLC0415
        from ..core.lowering import Lowered, resolve_ref_color  # noqa: PLC0415
        from ..core.marks import (  # noqa: PLC0415
            PolygonMark,
            Polyline,
            Stroke,
            TextMark,
        )

        color = resolve_ref_color(self.color, ctx.theme)
        stroke = Stroke(color, width=1.0, alpha=self.alpha)
        radii = [self.r_max * i / self.rings for i in range(1, self.rings + 1)]
        ring_pts = []
        for rr in radii:  # NaN row separates the closed outlines
            ring_pts.append(ellipse_points(0.0, 0.0, rr, rr))
            ring_pts.append(np.array([[np.nan, np.nan]]))
        rings_xy = np.concatenate(ring_pts[:-1])
        angles = [2.0 * np.pi * k / self.spokes for k in range(self.spokes)]
        sx = np.ravel([(0.0, self.r_max * np.cos(t)) for t in angles])
        sy = np.ravel([(0.0, self.r_max * np.sin(t)) for t in angles])
        marks: list = [
            PolygonMark(rings_xy[:, 0], rings_xy[:, 1], stroke=stroke),
            Polyline(sx, sy, stroke, connect="pairs"),
        ]
        if self.theta_labels is not False:
            for k, t in enumerate(angles):
                text = (f"{round(np.degrees(t))%360:g}°"
                        if self.theta_labels is True else self.theta_labels[k])
                marks.append(TextMark(1.12 * self.r_max * float(np.cos(t)),
                                      1.12 * self.r_max * float(np.sin(t)),
                                      text, color=color))
        if self.r_labels:
            for rr in radii:
                marks.append(TextMark(0.04 * self.r_max, rr, f"{rr:g}",
                                      color=color, halign="left"))
        return Lowered(marks=tuple(marks), legend=None)


def polar(element, *, theta: Accessor | None = None, r: Accessor | None = None):
    """Reinterpret a tabular element's position channels as polar
    ([D119] Option B): `x` becomes θ (radians, CCW from +x) and `y` becomes
    r unless `theta=`/`r=` name other bindings; the returned copy plots
    `(r·cosθ, r·sinθ)`. Column-name / `col()` bindings compose into a
    serializable `Expression` (lazy-capable, value-equal); a callable or
    raw-array binding falls back to a callable pair ([D14] escape-hatch
    semantics). Pair with `PolarGrid` and `.opts(aspect=1)`."""
    if getattr(element, "DATA_KIND", None) != "tabular" or \
            getattr(element, "CHANNELS", None) != ("x", "y"):
        raise ValidationError(
            f"polar() transforms elements whose x/y are per-row positions "
            f"(CHANNELS == ('x', 'y') — Scatter, Curve, Stem, …); "
            f"{type(element).__name__} does not qualify")
    th = theta if theta is not None else element.x
    rr = r if r is not None else element.y

    def _exprish(a):
        return col(a) if isinstance(a, str) else a if isinstance(a, Expr) else None

    the, rre = _exprish(th), _exprish(rr)
    if the is not None and rre is not None:  # the serializable arm
        return element.with_(x=rre * the.cos(), y=rre * the.sin())

    def _values(a, d):
        if isinstance(a, str):  # container-as-namespace: dict / DataFrame /
            return np.asarray(d[a])  # polars all getitem by column name
        if isinstance(a, Expr):
            return np.asarray(a.resolve(d))
        if callable(a):
            return np.asarray(a(d))
        return np.asarray(a)

    def _x(d, _t=th, _r=rr):
        return _values(_r, d) * np.cos(_values(_t, d))

    def _y(d, _t=th, _r=rr):
        return _values(_r, d) * np.sin(_values(_t, d))

    return element.with_(x=_x, y=_y)


def wedge(theta0: float, theta1: float, r0: float = 0.0, r1: float = 1.0, *,
          steps: int = 16) -> tuple[tuple[float, float], ...]:
    """Annulus-sector outline points — the polar bar, ready for
    `Polygon(wedge(...), fill=True)`: outer arc θ0→θ1 at `r1`, inner arc
    back at `r0` (a point when `r0 == 0`)."""
    if not float(r1) > float(r0) >= 0.0:
        raise ValidationError(
            f"wedge needs 0 <= r0 < r1, got r0={r0!r}, r1={r1!r}")
    if int(steps) < 2:
        raise ValidationError(f"wedge steps must be >= 2, got {steps!r}")
    ts = np.linspace(float(theta0), float(theta1), int(steps))
    outer = [(float(r1 * np.cos(t)), float(r1 * np.sin(t))) for t in ts]
    inner = [(float(r0 * np.cos(t)), float(r0 * np.sin(t))) for t in ts[::-1]]
    return tuple(outer + inner)
