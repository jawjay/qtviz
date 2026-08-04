"""Encoding — color and size by a data column, with automatic legends.

Bind `color_by` / `size_by` to a column and qtviz maps it to per-point color/size
and adds a legend for you:
  - a **categorical** column → a color key (one swatch per category)
  - a **numeric** column     → a continuous ramp + a colorbar

The mapping is the same data → color rule the Datashader path uses, so a column
colors consistently however it is drawn. The same `Element` works on both backends
(`backend="matplotlib"` gives a native mpl legend / colorbar).

Run:
    uv run python examples/12_color_mapping.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build():
    rng = np.random.default_rng(7)
    n = 1500
    data = {
        "x": rng.normal(size=n),
        "y": rng.normal(size=n),
        "mag": rng.uniform(0.0, 100.0, n),
        "kind": np.array(["alpha", "beta", "gamma", "delta"])[rng.integers(0, 4, n)],
    }
    by_category = qv.Scatter(data, x="x", y="y", color_by="kind", size=7)   # categorical → key
    by_value = qv.Scatter(data, x="x", y="y", color_by="mag", size_by="mag")  # numeric → colorbar
    return qv.View(by_category + by_value, theme=qv.Theme.dark())


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build(), title="qtviz — color & size encoding", size=(1000, 480))


if __name__ == "__main__":
    main()
