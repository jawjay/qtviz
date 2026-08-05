"""Interaction — typed events from native Qt interaction.

Subscribe to typed events with `view.on(EventType, handler)`. Try it:
  - **drag** to pan, **wheel** to zoom  → RangeEvent (throttled)
  - **Shift + drag** to rubber-band      → SelectEvent (brushed row indices)
  - **click a point**                    → PickEvent
Events print to the console.

Run:
    uv run python examples/05_interaction.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build():
    rng = np.random.default_rng(2)
    data = {"x": rng.normal(size=3000), "y": rng.normal(size=3000)}
    view = qv.View(qv.Scatter(data, x="x", y="y", size=4))

    view.on(qv.SelectEvent, lambda e: print(f"brushed {len(e.indices)} points  bounds={e.bounds}"))
    view.on(qv.PickEvent, lambda e: print(f"picked #{e.point_index} at ({e.x:.2f}, {e.y:.2f})"))
    view.on(qv.RangeEvent, lambda e: print(f"viewport x={e.x[0]:.2f}..{e.x[1]:.2f}"))
    return view


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build, title="qtviz — interaction (Shift+drag to brush)", size=(700, 700))


if __name__ == "__main__":
    main()
