"""qtviz — drive a HoloViews `DynamicMap` with a native Qt control (3b, [D44] L1).

A `DynamicMap` is a lazy, callback-driven HoloViews object. `from_holoviews_dmap`
turns it into a `(node_signal, kdim_signals)` binding: the node is a `Signal[Node]`
the View re-renders on change, and each kdim is a writable `Signal`. Setting a kdim
signal re-resolves the map and re-renders — one-way reactivity, no browser.

`kdim_panel` is the turnkey version (View + a slider/combo per kdim); the lower
block shows the composable primitive you'd use to build your own UI.

Run:
    uv run python examples/23_from_holoviews_dynamicmap.py
"""

from __future__ import annotations

import holoviews as hv
import numpy as np

import qtviz as qv
from qtviz.adapter.widgets import kdim_panel


def _sine_dmap():
    """A Curve whose frequency is a continuous kdim over (1, 10)."""
    xs = np.linspace(0.0, 10.0, 400)

    def curve(freq):
        return hv.Curve((xs, np.sin(freq * xs)), "x", "y")

    return hv.DynamicMap(curve, kdims=["freq"]).redim.range(freq=(1.0, 10.0))


def build(theme: qv.Theme | None = None):
    """Turnkey: a View + a `freq` slider, wired by `kdim_panel`."""
    return kdim_panel(_sine_dmap(), backend="pyqtgraph", theme=theme or qv.Theme.dark())


def build_composable():
    """The primitive: drive the kdim Signal yourself (here, programmatically)."""
    binding = qv.from_holoviews_dmap(_sine_dmap())
    view = qv.View(binding.node, backend="pyqtgraph")
    binding.kdims["freq"].set(7.5)  # any app UI can do this
    return view, binding


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    panel = build()
    panel.resize(900, 520)
    panel.setWindowTitle("qtviz — from_holoviews DynamicMap")
    panel.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
