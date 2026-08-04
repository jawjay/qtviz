"""qtviz — a pandas `.hvplot` one-liner rendered as a native Qt widget (3b, [D43]).

hvplot's fluent call (`df.hvplot.scatter(...)`) *returns* a HoloViews object; it is
only rendered to Bokeh when displayed. So `qv.from_hvplot` lets hvplot build the
object, then translates it through the same adapter — a native pyqtgraph widget,
no browser. `from_hvplot(df, "scatter", ...)` == `from_holoviews(df.hvplot(...))`.

Requires the optional extra:  pip install 'qtviz[hvplot]'

Run:
    uv run python examples/24_from_hvplot.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import qtviz as qv


def build(theme: qv.Theme | None = None):
    """`df.hvplot(kind="scatter")` muscle memory → a native qtviz View."""
    x = np.linspace(0.0, 10.0, 500)
    df = pd.DataFrame({"x": x, "y": np.sin(x) + np.random.default_rng(0).normal(0, 0.1, x.size)})

    node = qv.from_hvplot(df, "scatter", x="x", y="y")  # hvplot builds, adapter translates
    return qv.View(node, backend="pyqtgraph", theme=theme or qv.Theme.dark())


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build(), title="qtviz — from_hvplot", size=(900, 480))


if __name__ == "__main__":
    main()
