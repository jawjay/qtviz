"""qtviz — hover to inspect a datashaded view ([D46]).

A datashaded scatter is a density raster, not points — so qtviz retains the
per-pixel aggregate and reports the value under the cursor as `HoverEvent.value`.
Move the mouse over the plot and the count beneath it prints; the value stays
correct as you pan/zoom (the 4b controller refreshes the aggregate).

Run:
    uv run python examples/25_raster_inspect.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build(theme: qv.Theme | None = None):
    """A 1M-point datashaded scatter that reports `count` under the cursor."""
    rng = np.random.default_rng(0)
    n = 1_000_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n)}
    view = qv.View(
        qv.Scatter(data, x="x", y="y", raster="datashader"),
        backend="pyqtgraph", theme=theme or qv.Theme.dark(),
    )

    def on_hover(ev: qv.HoverEvent) -> None:
        if ev.value is not None:
            print(f"count at ({ev.x:.2f}, {ev.y:.2f}): {ev.value:.0f}")

    view.on(qv.HoverEvent, on_hover)
    return view


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(800, 600)
    view.setWindowTitle("qtviz — raster inspect (hover for count)")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
