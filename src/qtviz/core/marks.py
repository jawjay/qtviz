"""The Mark vocabulary — the typed IR between core lowering and backend drawing
([D121]/[D122], `design/2.0-mark-ir-and-surface.md`).

A Mark is a small frozen value object that says "draw this" in backend-neutral
terms. Positions are always **linear data space** (or axes-fraction where a
field says so) — the log pretransform pyqtgraph needs is that adapter's
concern, applied at draw time ([D121]). Style rides on **resolved**
`Stroke`/`Fill` — theme and palette slot applied during lowering — because
"the option survived into the mark" is only checkable if the mark records the
outcome ([D123]). Angles are CCW degrees ([D96]); per-engine sign flips live
in the adapters, stated once each.

Array-carrying marks set `eq=False`: ndarrays break dataclass equality, and a
mark must never masquerade as a value-hashed object. Structural comparison —
the [D123] honesty primitive — is `structurally_equal`.
"""

from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from dataclasses import fields as _dc_fields
from typing import Literal

import numpy as np

from .color import Color

Space = Literal["data", "axes"]  # axes = 0..1 surface fraction


def _arr(v) -> np.ndarray:
    return np.asarray(v, dtype="float64")


@dataclass(frozen=True)
class Stroke:
    """Resolved line style. `width` is px/pt (engine-native units, like today);
    the default is the [D132] uniform 1.5. `dash` is a named style or a dash
    tuple in points ([D99])."""

    color: Color
    width: float = 1.5
    dash: str | tuple[float, ...] = "solid"
    alpha: float = 1.0


@dataclass(frozen=True)
class Fill:
    color: Color
    alpha: float = 1.0


@dataclass(frozen=True, eq=False)
class Polyline:
    """NaN-gapped polyline(s). `connect="pairs"` draws independent segments
    (point 0→1, 2→3, …) without NaN separators — ErrorBars whiskers."""

    x: np.ndarray
    y: np.ndarray
    stroke: Stroke
    connect: Literal["finite", "pairs"] = "finite"
    step: Literal["pre", "post", "mid"] | None = None
    fill_to: float | None = None  # baseline fill (simple Area case)
    fill: Fill | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _arr(self.x))
        object.__setattr__(self, "y", _arr(self.y))


@dataclass(frozen=True, eq=False)
class Markers:
    """A point set. `size`/`fill` may be per-point arrays (sizes in pt;
    fill as N×4 RGBA floats); `pickable` marks the set index-addressable for
    hover/pick wiring ([D124] — the declared replacement for isinstance
    tuples in backend event code)."""

    x: np.ndarray
    y: np.ndarray
    marker: str = "circle"  # the curated 10-name vocabulary ([D132])
    size: float | np.ndarray = 7.0
    fill: Color | np.ndarray | None = None
    edge: Stroke | None = None
    alpha: float = 1.0
    pickable: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _arr(self.x))
        object.__setattr__(self, "y", _arr(self.y))


@dataclass(frozen=True, eq=False)
class Band:
    """Fill between two curves along `pos` — Spread, Area groups, Violin
    bodies (`orient="h"`)."""

    pos: np.ndarray  # x when orient="v", y when orient="h"
    lo: np.ndarray
    hi: np.ndarray
    fill: Fill
    orient: Literal["v", "h"] = "v"
    stroke: Stroke | None = None  # optional edge lines

    def __post_init__(self) -> None:
        for name in ("pos", "lo", "hi"):
            object.__setattr__(self, name, _arr(getattr(self, name)))


@dataclass(frozen=True, eq=False)
class TextMark:
    """Positioned text. `mask` is the [D117] contour-label device: a data-space
    segment `(x0, y0, x1, y1)` the adapter erases under the text with a
    background-colored stroke of `mask_width` px."""

    x: float
    y: float
    text: str
    color: Color
    size: float | None = None  # None = the engine's default font size
    anchor: Literal["left", "center", "right"] = "center"
    anchor_v: Literal["top", "center", "bottom"] = "center"
    rotation: float = 0.0  # CCW degrees ([D96]); adapters own engine sign flips
    frame: bool = False
    space: Space = "data"
    mask: tuple[float, float, float, float] | None = None
    mask_width: float = 9.0


@dataclass(frozen=True, eq=False)
class Rects:
    """Axis-aligned rectangle set — Histogram/Bars bars, BoxPlot boxes.
    `fill` may be per-rect (N×4 RGBA). `labels` carries [D131] `annotate=`
    text riding on the rects."""

    x0: np.ndarray
    x1: np.ndarray
    y0: np.ndarray
    y1: np.ndarray
    fill: Fill | np.ndarray | None = None
    stroke: Stroke | None = None
    labels: tuple[TextMark, ...] = ()

    def __post_init__(self) -> None:
        for name in ("x0", "x1", "y0", "y1"):
            object.__setattr__(self, name, _arr(getattr(self, name)))


@dataclass(frozen=True, eq=False)
class PolygonMark:
    """Closed outline(s), NaN-separated — Rect/Ellipse/Polygon annotations
    (via the `_geometry` point builders), later Pie wedges ([D127])."""

    x: np.ndarray
    y: np.ndarray
    stroke: Stroke | None = None
    fill: Fill | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _arr(self.x))
        object.__setattr__(self, "y", _arr(self.y))


@dataclass(frozen=True)
class Rule:
    """An infinite line — needs no viewport in the mark. `orient="slope"`
    reads `at` as intercept with `slope` set (RefLine); `span` optionally
    clips to a data-space extent (Span edges do not use this — see
    `SpanMark`)."""

    orient: Literal["h", "v", "slope"]
    stroke: Stroke
    at: float = 0.0
    slope: float | None = None
    span: tuple[float, float] | None = None


@dataclass(frozen=True)
class SpanMark:
    """A shaded horizontal/vertical region between `lo` and `hi`."""

    orient: Literal["h", "v"]
    lo: float
    hi: float
    fill: Fill


@dataclass(frozen=True)
class ArrowMark:
    """A point-to-point connector with **engine-native** (screen-space)
    arrowheads — deliberately not data-space polylines like Quiver's, so heads
    keep their size under zoom ([D96]). Each adapter draws its engine's arrow
    primitive; that per-engine head styling is the one drawing fact this mark
    does not pin."""

    x0: float
    y0: float
    x1: float
    y1: float
    stroke: Stroke
    head: Literal["end", "both", "none"] = "end"


Mark = (Polyline | Markers | Band | Rects | PolygonMark | TextMark
        | Rule | SpanMark | ArrowMark)

# The closed vocabulary. A backend's MARK_DRAWERS must be total over this
# tuple (guard-tested from wave 2 on): a mark a backend cannot draw is a
# registration-time error, never a silent drop.
MARK_TYPES: tuple[type, ...] = (
    Polyline, Markers, Band, Rects, PolygonMark, TextMark, Rule, SpanMark, ArrowMark,
)


def structurally_equal(a, b) -> bool:
    """Field-wise structural comparison — the [D123] honesty primitive.

    Deliberately a function, not `__eq__`, so ndarray-carrying marks never
    look value-hashable. Recurses through dataclasses (marks, `Stroke`,
    `Lowered`, `LegendEntry`) and tuples; ndarrays compare via
    `np.array_equal` (NaN-aware for float dtypes); everything else `==`.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, np.ndarray):
        equal_nan = a.dtype.kind == "f" and b.dtype.kind == "f"
        return bool(np.array_equal(a, b, equal_nan=equal_nan))
    if is_dataclass(a) and not isinstance(a, type):
        return all(
            structurally_equal(getattr(a, f.name), getattr(b, f.name))
            for f in _dc_fields(a)
        )
    if isinstance(a, tuple):
        return len(a) == len(b) and all(
            structurally_equal(x, y) for x, y in zip(a, b, strict=True)
        )
    return bool(a == b)
