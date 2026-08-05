"""Inset axes — a zoom window floating on its parent ([D152]–[D154],
design/inset-axes.md).

`qv.Inset(child, rect=…)` composes into an overlay like an annotation: the
child is a full surface (own title, lims via `.opts()`), `rect` places it in
axes-fraction coordinates, and `indicate=True` draws the parent-side
rectangle marking the child's declared window. A **labeled** inset is a pane
— the same machinery as grid panes:

    view.pane("zoom").set_range(x=(20, 22))   # move the zoom window
    view.on(qv.RangeEvent, cb, pane="zoom")   # events from inside the inset
    view.pane("zoom").export("zoom.png")      # just the inset

and its window survives rebuilds and `set_backend()` switches. Renders on
pyqtgraph and matplotlib; webengine warns-and-skips insets for now.

Run:
    uv run python examples/38_inset_zoom.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv

rng = np.random.default_rng(3)
t = np.linspace(0.0, 30.0, 800)
v = np.sin(t) + 0.1 * np.sin(40.0 * t) + rng.normal(0.0, 0.03, t.size)
d = {"t": t, "v": v}

overview = qv.Curve(d, x="t", y="v").opts(
    title="Signal — with a zoom inset", x="t [s]")
zoom = qv.Curve(d, x="t", y="v").opts(
    title="12–14 s",
    x=qv.AxisSpec(lim=(12.0, 14.0)),
    y=qv.AxisSpec(lim=(-1.4, 1.4)),
)
root = overview * qv.Inset(zoom, rect=(0.58, 0.55, 0.4, 0.42),
                           label="zoom", indicate=True)


def build() -> qv.View:
    return qv.View(root, backend="pyqtgraph")


def main() -> None:
    view = build()
    view.on(qv.RangeEvent,
            lambda e: print(f"zoom window: x={e.x[0]:.2f}..{e.x[1]:.2f}"),
            pane="zoom", throttle_ms=200)
    qv.show(view, title="qtviz — inset zoom", size=(950, 560))


if __name__ == "__main__":
    main()
