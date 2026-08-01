"""Shared annotation geometry ([D97]/[D110]) — computed once in core so every
backend draws the same outline. Pure numpy, no Qt."""

from __future__ import annotations

import numpy as np


def ellipse_points(cx: float, cy: float, rx: float, ry: float,
                   angle: float = 0.0, n: int = 72) -> np.ndarray:
    """`(n, 2)` closed outline of a rotated ellipse (first point repeated last).
    Rotation is counter-clockwise degrees about the center — the mpl `Ellipse`
    convention."""
    t = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    x, y = rx * np.cos(t), ry * np.sin(t)
    rad = np.deg2rad(angle)
    c, s = np.cos(rad), np.sin(rad)
    pts = np.column_stack([cx + x * c - y * s, cy + x * s + y * c])
    return np.vstack([pts, pts[:1]])


def rect_points(x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """`(5, 2)` closed rectangle outline."""
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]])


def close_points(points) -> np.ndarray:
    """A polygon's points as a closed `(n+1, 2)` array."""
    pts = np.asarray(points, dtype="float64")
    return np.vstack([pts, pts[:1]])


def svg_path(points) -> str:
    """A closed SVG path string for a Plotly `layout.shapes` path entry."""
    pts = np.asarray(points, dtype="float64")
    body = " L ".join(f"{x:g},{y:g}" for x, y in pts)
    return f"M {body} Z"


_HEAD_ANGLE = np.deg2rad(25.0)


def quiver_scale(x, y, u, v) -> float:
    """The "auto" arrow scale ([D107]): the typical cell of the field
    (√(span_area / n)) should hold the largest arrow at ~90%."""
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    mag = np.hypot(np.asarray(u, dtype="float64"), np.asarray(v, dtype="float64"))
    max_mag = float(np.nanmax(mag)) if len(mag) else 0.0
    if max_mag == 0.0:
        return 1.0
    span_x = (float(np.nanmax(x)) - float(np.nanmin(x))) or 1.0
    span_y = (float(np.nanmax(y)) - float(np.nanmin(y))) or 1.0
    cell = np.sqrt(span_x * span_y / max(len(x), 1))
    return 0.9 * cell / max_mag


def limit_arrow_segments(x, y, err_lo, err_hi, lo_limit, hi_limit, *,
                         direction: str = "y"):
    """ErrorBars limit arrows ([D116]): where a limit flag is true, that
    side's bar becomes an arrow from the datum to the bar end — "the true
    value lies beyond". Each is literally a quiver arrow (`u`/`v` = the
    signed error), so heads share the [D107] construction: ±25° barbs, 30%
    of the bar, in data space. Returns the same `(shaft, head)` NaN-separated
    polyline pair `quiver_segments` emits (empty arrays when no flags)."""
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    xs, ys, us, vs = [], [], [], []
    for mask, sign, err in ((lo_limit, -1.0, err_lo), (hi_limit, 1.0, err_hi)):
        if mask is None:
            continue
        m = np.asarray(mask, dtype=bool)
        if not m.any():
            continue
        e = np.asarray(err, dtype="float64")[m] * sign
        zeros = np.zeros(int(m.sum()))
        xs.append(x[m])
        ys.append(y[m])
        us.append(e if direction == "x" else zeros)
        vs.append(zeros if direction == "x" else e)
    if not xs:
        empty = np.empty(0)
        return (empty, empty.copy()), (empty.copy(), empty.copy())
    return quiver_segments(np.concatenate(xs), np.concatenate(ys),
                           np.concatenate(us), np.concatenate(vs), 1.0)


def stem_segments(x, y, baseline: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Stem geometry ([D115]): per-point vertical segments
    `(x, baseline) → (x, y)` as pair-connected arrays — index 2i is the foot,
    2i+1 the head, so pg draws them with one `connect="pairs"` item and the
    other backends reshape to `(n, 2)` segments / NaN-gapped polylines."""
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    sx = np.repeat(x, 2)
    sy = np.column_stack([np.full(len(y), float(baseline)), y]).ravel()
    return sx, sy


def arrow_key_points(head_scale: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """The quiver legend key's sample glyph ([D112]): one unit arrow along +x,
    built by `quiver_segments` itself — same ±25° barbs, same 30% head — so the
    sample is truthful by construction. Returns `(shaft, head)` as `(2, 2)` and
    `(3, 2)` point arrays in the unit box; backends scale it into their legend
    sample box (the *magnitude* is stated by the entry label, since a
    data-space pixel length would go stale on zoom and Plotly cannot draw a
    custom sample at all)."""
    zero, one = np.zeros(1), np.ones(1)
    (sx, sy), (hx, hy) = quiver_segments(zero, zero, one, zero, 1.0, head_scale)
    return (np.column_stack([sx[:2], sy[:2]]),
            np.column_stack([hx[:3], hy[:3]]))


def quiver_segments(x, y, u, v, scale: float, head_scale: float = 1.0):
    """Shared arrow geometry ([D107]/[D110]): `(shaft_xy, head_xy)` as
    NaN-separated polylines every backend draws with two cheap primitives —
    pixel-identical fields everywhere, and no thousand arrow items. Heads are
    two barbs at ±25° whose length is 30% of each arrow (× `head_scale`),
    in data space (they zoom with the field)."""
    x = np.asarray(x, dtype="float64")
    y = np.asarray(y, dtype="float64")
    dx = np.asarray(u, dtype="float64") * scale
    dy = np.asarray(v, dtype="float64") * scale
    tip_x, tip_y = x + dx, y + dy
    n = len(x)
    nan = np.full(n, np.nan)
    shaft_x = np.column_stack([x, tip_x, nan]).ravel()
    shaft_y = np.column_stack([y, tip_y, nan]).ravel()
    theta = np.arctan2(dy, dx)
    barb = 0.3 * np.hypot(dx, dy) * head_scale
    left_x = tip_x - barb * np.cos(theta - _HEAD_ANGLE)
    left_y = tip_y - barb * np.sin(theta - _HEAD_ANGLE)
    right_x = tip_x - barb * np.cos(theta + _HEAD_ANGLE)
    right_y = tip_y - barb * np.sin(theta + _HEAD_ANGLE)
    head_x = np.column_stack([left_x, tip_x, right_x, nan]).ravel()
    head_y = np.column_stack([left_y, tip_y, right_y, nan]).ravel()
    return (shaft_x, shaft_y), (head_x, head_y)
