"""Polar plots — a transform, not a projection ([D119],
design/spikes/polar-spike-report.md).

`qv.polar(element)` reinterprets x/y as (θ, r) — radians, CCW from +x —
and plots `(r·cosθ, r·sinθ)`; `qv.PolarGrid(r_max)` draws the circular
chrome (rings, spokes, degree or custom labels); `qv.wedge(...)` builds
annulus-sector points for `Polygon` polar bars. The surface stays
rectilinear — pair with `.opts(aspect=1, grid=False)` and
`AxisSpec(ticks=())` — so pan/zoom, brushes, view state, and backend
switching all keep working; the readout trade-offs are recorded in the
spike report.

Run:
    uv run python examples/39_polar.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def frame(node, r_max: float, title: str):
    pad = 1.35 * r_max
    return node.opts(title=title, aspect=1.0, grid=False,
                     x=qv.AxisSpec(lim=(-pad, pad), ticks=()),
                     y=qv.AxisSpec(lim=(-pad, pad), ticks=()))


# ── spiral: qv.polar() on an ordinary Curve ─────────────────────────────────
r = np.arange(0.0, 2.0, 0.01)
spiral = qv.polar(qv.Curve({"theta": 2.0 * np.pi * r, "r": r},
                           x="theta", y="r", line_width=2.0))
polar_demo = frame(qv.PolarGrid(2.0) * spiral, 2.0, "spiral — qv.polar(Curve)")

# ── polar bars: wedges via qv.wedge() + Polygon ─────────────────────────────
rng = np.random.default_rng(19680801)
n = 20
heights = 10.0 * rng.random(n)
bars = qv.PolarGrid(10.0, rings=5, r_labels=False)
for i in range(n):
    th0 = 2.0 * np.pi * i / n
    color = qv.Theme.light().palette[i % len(qv.Theme.light().palette.colors)]
    bars = bars * qv.Polygon(
        qv.wedge(th0, th0 + 2.0 * np.pi / n * 0.9, 0.0, float(heights[i])),
        color=color, fill=True, alpha=0.6)
polar_bar = frame(bars, 10.0, "polar bars — qv.wedge()")

# ── radar: custom spoke labels + filled value polygons ──────────────────────
cats = ("speed", "power", "range", "cost", "size")
th = np.array([2.0 * np.pi * i / len(cats) for i in range(len(cats))])
radar = qv.PolarGrid(5.0, rings=5, spokes=len(cats), r_labels=False,
                     theta_labels=cats)
palette = qv.Theme.light().palette
for i, (vals, label) in enumerate((((4, 3, 5, 2, 4), "unit A"),
                                   ((2, 5, 3, 4, 3), "unit B"))):
    pts = [(float(v * np.cos(t)), float(v * np.sin(t)))
           for v, t in zip(vals, th, strict=True)]
    radar = radar * qv.Polygon(pts, fill=True, alpha=0.35, label=label,
                               color=palette[i])
radar_chart = frame(radar, 5.0, "radar — custom theta_labels")

root = qv.Layout([polar_demo, polar_bar, radar_chart], kind="grid",
                 options=qv.LayoutOptions(rows=1, cols=3))


def build() -> qv.View:
    return qv.View(root, backend="matplotlib")


def main() -> None:
    qv.show(build(), title="qtviz — polar", size=(1380, 500))


if __name__ == "__main__":
    main()
