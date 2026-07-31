"""The everyday figures — the parity-program vocabulary in one window.

Eight panels, one Element tree: a step curve with markers, a stacked area,
horizontal grouped bars, a donut, an ECDF, filled contours, a dual-axis
telemetry pair, and SI/percent tick formatting ([D83]–[D95],
design/parity-program.md). Everything here warns-or-honors per backend —
swap `BACKEND` to "pyqtgraph" or "webengine" and the same tree renders
(the pie routes itself to a capable backend automatically).

Run:
    uv run python examples/35_everyday_figures.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QApplication

import qtviz as qv

BACKEND = "matplotlib"

rng = np.random.default_rng(7)
t = np.linspace(0.0, 10.0, 200)

# 1 — step curve with markers ([D84])
steps = {"x": np.arange(12.0), "y": rng.integers(1, 9, 12).astype(float)}
step_panel = qv.Overlay(
    [qv.Curve(steps, x="x", y="y", step="post", marker="circle", label="requests")],
    options=qv.OverlayOptions(title="Step curve"),
)

# 2 — stacked area ([D84b])
area = {
    "t": np.tile(t, 3),
    "load": np.concatenate([2 + np.sin(t), 1.5 + 0.5 * np.cos(t), 1 + 0.3 * t / 10]),
    "svc": np.repeat(["api", "worker", "cron"], len(t)),
}
area_panel = qv.Overlay(
    [qv.Area(area, x="t", y="load", group="svc", mode="stacked", alpha=0.85)],
    options=qv.OverlayOptions(title="Stacked area"),
)

# 3 — horizontal grouped bars ([D85])
bars = {"region": ["north", "south", "east", "west"] * 2,
        "sales": [40.0, 65, 52, 30, 55, 45, 60, 42],
        "year": ["2025"] * 4 + ["2026"] * 4}
bars_panel = qv.Overlay(
    [qv.Bars(bars, x="region", y="sales", group="year", orient="h")],
    options=qv.OverlayOptions(title="Horizontal grouped bars"),
)

# 4 — donut ([D90]; matplotlib/webengine — negotiation routes around pyqtgraph)
pie_panel = qv.Overlay(
    [qv.Pie({"share": [42.0, 31.0, 17.0, 10.0],
             "browser": ["chrome", "safari", "firefox", "other"]},
            values="share", labels="browser", hole=0.45)],
    options=qv.OverlayOptions(title="Donut"),
)

# 5 — ECDF ([D91])
latencies = {"ms": rng.lognormal(3.0, 0.4, 500)}
ecdf_panel = qv.Overlay(
    [qv.Ecdf(latencies, column="ms", label="latency")],
    options=qv.OverlayOptions(title="ECDF",
                              y=qv.AxisSpec(tick_format=".0%")),  # ([D86])
)

# 6 — filled contours ([D89])
gy, gx = np.mgrid[-3:3:80j, -3:3:120j]
field = np.exp(-(gx**2 + gy**2) / 2) + 0.6 * np.exp(-((gx - 1.5) ** 2 + (gy + 1) ** 2))
contour_panel = qv.Overlay(
    [qv.Contour(field, bounds=(-3, -3, 3, 3), levels=8, filled=True)],
    options=qv.OverlayOptions(title="Filled contour"),
)

# 7 — dual axis ([D88])
telemetry = {"t": t, "temp": 20 + 4 * np.sin(t / 2),
             "pressure": 101_000 + 800 * np.cos(t / 3)}
dual_panel = qv.Overlay(
    [qv.Curve(telemetry, x="t", y="temp", label="°C"),
     qv.Curve(telemetry, x="t", y="pressure", axis="y2", label="Pa",
              line_style="dashed")],
    options=qv.OverlayOptions(title="Dual axis", y_label="°C",
                              y2=qv.AxisSpec(label="Pa", tick_format="eng")),
)

# 8 — SI ticks + grid off ([D86]/[D87])
traffic = {"t": t, "bytes": (1 + np.sin(t / 2) ** 2) * 2e6}
ticks_panel = qv.Overlay(
    [qv.Curve(traffic, x="t", y="bytes", label="throughput")],
    options=qv.OverlayOptions(title="SI ticks, no grid", grid=False,
                              y=qv.AxisSpec(tick_format="eng")),
)

root = qv.Layout(
    [step_panel, area_panel, bars_panel, pie_panel,
     ecdf_panel, contour_panel, ticks_panel, dual_panel],  # dual last: its right
    options=qv.LayoutOptions(cols=4),                      # axis gets the margin
)


def build() -> qv.View:
    return qv.View(root, backend=BACKEND, toolbar=True)  # ([D95])


def main() -> None:
    app = QApplication([])
    view = build()
    view.resize(1600, 800)
    view.setWindowTitle("qtviz — the everyday figures")
    view.show()
    app.exec()


if __name__ == "__main__":
    main()
