"""Axis labels & titles — configure any surface with `.opts()` ([D133]).

Call `.opts()` on any element or composition to give its surface a `title`
and axis labels — a bare string is the label; pass an `AxisSpec` for scales,
limits, and tick control. The same description renders identically on every
backend — pyqtgraph, matplotlib, and webengine — and, inside a `Layout`,
each pane keeps its own labels.

    points * trend                                   # an overlay (no labels)
    (points * trend).opts(
        title="Sensor response", x="drive (V)", y="output (mV)")

Try a different engine — the labels come out the same:
    qv.View(figure, backend="matplotlib")

Run:
    uv run python examples/31_axis_labels.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build(backend: str = "pyqtgraph"):
    rng = np.random.default_rng(7)
    v = np.linspace(0.0, 5.0, 120)              # drive voltage (V)
    fit = 2.5 * v + 8.0                          # ideal linear response
    out = fit + rng.normal(0.0, 3.0, v.size)    # measured output (mV)
    data = {"v": v, "out": out, "fit": fit, "resid": out - fit}

    # Panel 1 — an overlay with a labeled surface.
    measured = qv.Scatter(data, x="v", y="out", size=5, color="#5fa8ff")
    trend = qv.Curve(data, x="v", y="fit", color="#ff7f0e", line_width=2.0)
    response = qv.Overlay(
        [measured, trend],
        options=qv.OverlayOptions(
            title="Sensor response",
            x="drive voltage (V)",
            y="output (mV)",
        ),
    )

    # Panel 2 — even a single element gets labels by wrapping it in an Overlay.
    residuals = (qv.Histogram(data, value="resid", color="#7bd47b")
        ).opts(title="Residuals", x="error (mV)", y="count")

    # Two panes side by side — each keeps its own title and axis labels.
    figure = qv.Layout([response, residuals], options=qv.LayoutOptions(cols=2))
    return qv.View(figure, backend=backend, theme=qv.Theme.dark())


def main() -> None:
    # try build(backend="matplotlib") — the labels come out the same
    qv.show(build(), title="qtviz — axis labels & titles", size=(1000, 480))


if __name__ == "__main__":
    main()
