"""RawFigure + HoloViews — host a HoloViews figure, get qtviz typed events.

The webengine backend renders a HoloViews object through Bokeh, and (W3b) bridges
Bokeh's tap / box-select / range interactions back as the *same* qtviz typed
events the native backends emit. So a HoloViews figure dropped into a qtviz `View`
via `RawFigure` participates in `view.on(...)` like any other element.

Use the **tap** and **box-select** tools in the toolbar:
  - tap a point      → TapEvent (x, y)
  - box-select       → SelectEvent (the brushed region's bounds)
  - pan / zoom       → RangeEvent
Events print to the console.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`,
which includes HoloViews + Bokeh) and renders fully offline (JS bundled, no CDN);
it will not run headless.

Run:
    uv run python examples/19_webengine_holoviews.py
"""

from __future__ import annotations

import holoviews as hv
import numpy as np

import qtviz as qv

hv.extension("bokeh")


def build():
    rng = np.random.default_rng(0)
    points = hv.Scatter((rng.normal(size=600), rng.normal(size=600))).opts(
        tools=["tap", "box_select"], size=6, width=820, height=560,
        title="a HoloViews scatter, hosted in qtviz",
    )

    view = qv.View(qv.RawFigure(points))  # backend="auto" → webengine
    view.on(qv.TapEvent, lambda e: print(f"tapped at ({e.x:.2f}, {e.y:.2f})"))
    view.on(qv.SelectEvent, lambda e: print(f"selected region extent={e.bounds}"))
    view.on(qv.RangeEvent, lambda e: print(f"viewport x={e.x[0]:.2f}..{e.x[1]:.2f}"))
    return view


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build(), title="qtviz — RawFigure (HoloViews)", size=(880, 600))


if __name__ == "__main__":
    main()
