"""qtviz — render a HoloViews object through the native pyqtgraph backend.

`qv.from_holoviews` translates a HoloViews tree (elements + `*`/`+` composition)
into native qtviz Elements, so a HoloViews-fluent user gets a Qt-native widget in
one call — no browser, no Bokeh server. Coverage is the elements qtviz models;
the long tail falls back to a webengine `RawFigure`.

Run:
    uv run python examples/22_from_holoviews.py
"""

from __future__ import annotations

import holoviews as hv
import numpy as np
import pandas as pd

import qtviz as qv


def build(theme: qv.Theme | None = None):
    """Translate `hv.Scatter * hv.Curve + hv.Bars` to a native qtviz View."""
    x = np.linspace(0.0, 10.0, 400)
    df = pd.DataFrame({"x": x, "y": np.sin(x), "smooth": np.sin(x) * 0.9})
    bars = pd.DataFrame({"g": list("ABCD"), "v": [3.0, 1.0, 4.0, 2.0]})

    hv_obj = (hv.Scatter(df, "x", "y") * hv.Curve(df, "x", "smooth")) + hv.Bars(bars, "g", "v")

    node = qv.from_holoviews(hv_obj)  # ← the adapter: hv tree → qtviz Node
    return qv.View(node, backend="pyqtgraph", theme=theme or qv.Theme.dark())


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build, title="qtviz — from_holoviews", size=(1100, 450))


if __name__ == "__main__":
    main()
