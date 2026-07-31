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
