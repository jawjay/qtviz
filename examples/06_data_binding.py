"""Data binding — bind channels to names, Expressions, callables, or arrays.

A channel (`x`, `y`, …) accepts an **accessor**:
  - a column name           — `y="raw"`
  - a qtviz `Expression`    — `y=qv.col("raw") - qv.col("baseline")`  (serializable, lazy)
  - a callable              — `y=lambda d: d["raw"].cumsum()`        (arbitrary Python)
  - a literal array         — `x=np.linspace(0, 1, n)`
The string case is the easy default; the others let you derive channels without
reshaping your data first.

Run:
    uv run python examples/06_data_binding.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv


def build():
    n = 400
    t = np.linspace(0, 20, n)
    rng = np.random.default_rng(3)
    data = {"t": t, "baseline": 0.05 * t, "raw": 0.05 * t + np.sin(t) + rng.normal(0, 0.1, n)}

    raw = qv.Scatter(data, x="t", y="raw", size=3, color="#9aa0a6")
    # Expression: detrended signal = raw - baseline (serializable, pushdown-friendly)
    detrended = qv.Curve(data, x="t", y=qv.col("raw") - qv.col("baseline"), color="#5fa8ff",
                         line_width=2.0)
    # Callable: running mean via arbitrary Python
    smoothed = qv.Curve(data, x="t", y=lambda d: np.convolve(d["raw"], np.ones(15) / 15, "same"),
                        color="#ff7f0e", line_width=2.0)

    return qv.View(raw * detrended * smoothed, theme=qv.Theme.dark())


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build(), title="qtviz — data binding (string / Expression / callable)", size=(900, 520))


if __name__ == "__main__":
    main()
