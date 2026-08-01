"""Streamline integration ([D118], wave 1.5) — mpl's streamplot algorithm,
reimplemented small. Pure numpy, no Qt, no mpl.

Seeds walk a coarse spacing-mask grid (`30×30 · density`); each seed
integrates the *direction field* (velocity normalized to unit speed, bilinear
interpolation) with fixed-step RK4 in both directions, terminating on domain
exit, stagnation, or entry into an occupied mask cell — the mask is what
enforces line spacing. Kept lines commit their cells; short scraps are
discarded without claiming anything. Output is data-space polylines plus one
mid-line arrowhead each, built with the same ±25° construction as the [D107]
quiver heads — primitives every backend already draws.
"""

from __future__ import annotations

import numpy as np

_HEAD_ANGLE = np.deg2rad(25.0)  # the [D107] barb angle
_BASE_MASK = 30                 # mask cells per axis at density=1 (mpl's 30)
_STEP = 0.3                     # RK4 step, grid units (fraction of a grid cell)
# Discard scraps whose arc length is below this fraction of the smaller grid
# dimension (mpl's `minlength` analog) — short stubs read as noise, and a
# discarded scrap releases its cells for a longer neighbor.
_MIN_LEN_FRAC = 0.12


def _interp(field: np.ndarray, x: float, y: float) -> float:
    """Bilinear sample of `field[(row=y, col=x)]` at fractional grid coords."""
    ny, nx = field.shape
    i = min(max(int(x), 0), nx - 2)
    j = min(max(int(y), 0), ny - 2)
    fx, fy = x - i, y - j
    return float(field[j, i] * (1 - fx) * (1 - fy) + field[j, i + 1] * fx * (1 - fy)
                 + field[j + 1, i] * (1 - fx) * fy + field[j + 1, i + 1] * fx * fy)


def _mask_cells(points: np.ndarray, shape, bounds, density: float) -> set:
    """The spacing-mask cells a data-space polyline occupies (test seam)."""
    ny, nx = shape
    x0, y0, x1, y1 = bounds
    n = max(int(_BASE_MASK * density), 1)
    gx = (points[:, 0] - x0) / ((x1 - x0) or 1.0) * (nx - 1)
    gy = (points[:, 1] - y0) / ((y1 - y0) or 1.0) * (ny - 1)
    ci = np.clip((gx / max(nx - 1, 1) * n).astype(int), 0, n - 1)
    cj = np.clip((gy / max(ny - 1, 1) * n).astype(int), 0, n - 1)
    return set(zip(ci.tolist(), cj.tolist(), strict=True))


def streamline_paths(u, v, bounds, density: float = 1.0, *,
                     head_frac: float = 0.03):
    """Integrate the field into spaced streamlines: → `(paths, heads)` where
    `paths` is a list of `(n, 2)` data-space polylines and `heads` a matching
    list of `(3, 2)` arrowhead polylines (left barb, tip, right barb) at each
    line's arc-length midpoint. `head_frac` sizes the barbs as a fraction of
    the larger bounds span."""
    u = np.asarray(u, dtype="float64")
    v = np.asarray(v, dtype="float64")
    ny, nx = u.shape
    x0, y0, x1, y1 = (float(b) for b in bounds)
    n_mask = max(int(_BASE_MASK * density), 1)

    def cell(gx: float, gy: float) -> tuple[int, int]:
        return (min(int(gx / max(nx - 1, 1) * n_mask), n_mask - 1),
                min(int(gy / max(ny - 1, 1) * n_mask), n_mask - 1))

    def direction(gx: float, gy: float, sign: float):
        du, dv = _interp(u, gx, gy), _interp(v, gx, gy)
        speed = float(np.hypot(du, dv))
        if speed < 1e-12:
            return None  # stagnation
        return sign * du / speed, sign * dv / speed

    def rk4(gx: float, gy: float, sign: float):
        k1 = direction(gx, gy, sign)
        if k1 is None:
            return None
        k2 = direction(gx + 0.5 * _STEP * k1[0], gy + 0.5 * _STEP * k1[1], sign)
        if k2 is None:
            return None
        k3 = direction(gx + 0.5 * _STEP * k2[0], gy + 0.5 * _STEP * k2[1], sign)
        if k3 is None:
            return None
        k4 = direction(gx + _STEP * k3[0], gy + _STEP * k3[1], sign)
        if k4 is None:
            return None
        return (gx + _STEP * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0,
                gy + _STEP * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0)

    occupied: set = set()
    max_steps = int(4 * (nx + ny) / _STEP)

    def integrate(gx: float, gy: float, sign: float, line_cells: set) -> list:
        """One direction from the seed; returns grid-space points (seed excluded)."""
        pts: list = []
        cur = cell(gx, gy)
        for _ in range(max_steps):
            nxt = rk4(gx, gy, sign)
            if nxt is None:
                break  # stagnation inside the domain
            gx, gy = nxt
            if not (0.0 <= gx <= nx - 1 and 0.0 <= gy <= ny - 1):
                break  # left the domain
            c = cell(gx, gy)
            if c != cur:
                if c in occupied or c in line_cells:
                    break  # spacing (another line) or loop closure (our own)
                line_cells.add(c)
                cur = c
            pts.append((gx, gy))
        return pts

    paths: list[np.ndarray] = []
    heads: list[np.ndarray] = []
    sx = (x1 - x0) / max(nx - 1, 1)
    sy = (y1 - y0) / max(ny - 1, 1)
    head_len = head_frac * max(x1 - x0, y1 - y0)
    for cj in range(n_mask):
        for ci in range(n_mask):
            if (ci, cj) in occupied:
                continue
            gx = (ci + 0.5) / n_mask * (nx - 1)
            gy = (cj + 0.5) / n_mask * (ny - 1)
            line_cells = {cell(gx, gy)}
            fwd = integrate(gx, gy, +1.0, line_cells)
            bwd = integrate(gx, gy, -1.0, line_cells)
            grid_pts = bwd[::-1] + [(gx, gy)] + fwd
            if (len(grid_pts) - 1) * _STEP < _MIN_LEN_FRAC * min(nx - 1, ny - 1):
                continue  # a scrap — discard without claiming cells
            occupied.update(line_cells)
            arr = np.asarray(grid_pts, dtype="float64")
            data = np.column_stack([x0 + arr[:, 0] * sx, y0 + arr[:, 1] * sy])
            paths.append(data)
            heads.append(_mid_arrowhead(data, head_len))
    return paths, heads


def _mid_arrowhead(data: np.ndarray, head_len: float) -> np.ndarray:
    """`(3, 2)` barb polyline (left, tip, right) at the path's arc-length
    midpoint, oriented along the local direction — the [D107] construction."""
    d = np.hypot(*np.diff(data, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(d)])
    k = int(np.searchsorted(cum, cum[-1] / 2.0))
    k = min(max(k, 1), len(data) - 1)
    tip = (data[k - 1] + data[k]) / 2.0
    dx, dy = data[k] - data[k - 1]
    theta = float(np.arctan2(dy, dx))
    left = tip - head_len * np.array([np.cos(theta - _HEAD_ANGLE),
                                      np.sin(theta - _HEAD_ANGLE)])
    right = tip - head_len * np.array([np.cos(theta + _HEAD_ANGLE),
                                       np.sin(theta + _HEAD_ANGLE)])
    return np.vstack([left, tip, right])
