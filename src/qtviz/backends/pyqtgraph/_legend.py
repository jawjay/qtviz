"""pyqtgraph legend rendering for a `core.encoding.Legend`.

Categorical legends list a colored swatch per category. Continuous legends are
drawn as a small stepped colorbar — the ramp sampled at five stops with their
values — which reuses the same `LegendItem` swatch path and avoids the fragile
`GradientLegend` positioning. A true gradient colorbar is a refinement (tracked in
`capabilities-gaps.md`).
"""

from __future__ import annotations

import pyqtgraph as pg


def _ramp_entries(legend) -> list[tuple[str, object]]:
    stops = legend.ramp
    n = len(stops)
    if n < 2:
        return [(f"{legend.vmin:.3g}", stops[0])] if stops else []
    if not legend.linear:  # non-linear (eq_hist density): endpoints only, no interior ticks ([D48])
        return [(f"{legend.vmax:.3g}", stops[-1]), (f"{legend.vmin:.3g}", stops[0])]
    span = legend.vmax - legend.vmin
    return [(f"{legend.vmin + span * i / (n - 1):.3g}", stops[i]) for i in range(n)]


def add_legend(plot, legend, theme) -> None:
    """Draw (or replace) the legend for `plot`. Idempotent: a prior qtviz legend is
    removed first, so re-aggregating a datashaded view (C3) refreshes rather than
    stacks legends."""
    existing = getattr(plot, "_qtviz_legend", None)
    if existing is not None:
        scene = existing.scene()
        if scene is not None:
            scene.removeItem(existing)
        plot.legend = None
    lg = plot.addLegend(offset=(-10, 10))
    plot._qtviz_legend = lg
    entries = legend.entries if legend.kind == "categorical" else _ramp_entries(legend)
    for label, color in entries:
        swatch = pg.ScatterPlotItem([0], [0], brush=color.qt(), pen=None, size=10, symbol="s")
        lg.addItem(swatch, label)
