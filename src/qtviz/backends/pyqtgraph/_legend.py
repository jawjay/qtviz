"""pyqtgraph legend rendering for a `core.encoding.Legend`.

Categorical legends list a colored swatch per category. Continuous *linear*
legends are a true gradient `pg.ColorBarItem` inserted into the PlotItem's own
layout ([D55] parity — matches matplotlib's `figure.colorbar`). A non-linear
legend (eq_hist density) deliberately stays an endpoints-only swatch key: a
gradient bar would imply linear ticks the mapping doesn't have ([D48]).
"""

from __future__ import annotations

import numpy as np
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


# `legend_position` vocabulary → LegendItem offset (positive = from the top-left
# corner, negative = from the opposite edge). "top" approximates top-left;
# pyqtgraph has no native top-center anchor.
_OFFSET = {"auto": (-10, 10), "right": (-10, 10), "top": (10, 10)}


def add_legend(plot, legend, theme, position: str = "auto") -> None:
    """Draw (or replace) the color-mapping legend for `plot`. Idempotent: a prior
    qtviz legend is removed first, so re-aggregating a datashaded view (C3)
    refreshes rather than stacks legends."""
    if legend.kind == "continuous" and legend.linear:
        _add_colorbar(plot, legend, theme)
        return
    existing = getattr(plot, "_qtviz_legend", None)
    if existing is not None:
        scene = existing.scene()
        if scene is not None:
            scene.removeItem(existing)
        plot.legend = None
        plot._qtviz_legend = None
    lg = _ensure_legend(plot, position)
    entries = legend.entries if legend.kind == "categorical" else _ramp_entries(legend)
    for label, color in entries:
        _add_swatch(lg, label, color)


def append_legend_entries(plot, entries, theme, position: str = "auto") -> None:
    """Add the Overlay-aggregated `LegendEntry` contributions ([D60]) to the plot's
    legend — *merging* into an existing color-mapping legend (a `color_by` Scatter
    in the same Overlay) rather than replacing it, so a surface always shows one
    combined legend. An `"arrow"` glyph (the [D112] Quiver key) paints the core
    unit-arrow sample instead of a color square."""
    lg = _ensure_legend(plot, position)
    for e in entries:
        if getattr(e, "glyph", "swatch") == "arrow":
            lg.addItem(_ArrowSample(e), e.label)
        else:
            _add_swatch(lg, e.label, e.swatch)


def _ensure_legend(plot, position: str):
    lg = getattr(plot, "_qtviz_legend", None)
    if lg is None or lg.scene() is None:
        lg = plot.addLegend(offset=_OFFSET.get(position, (-10, 10)))
        plot._qtviz_legend = lg
    return lg


class _ArrowSample(pg.graphicsItems.LegendItem.ItemSample):
    """Legend sample for the Quiver reference key ([D112]): the core unit-arrow
    geometry (`arrow_key_points` — same barbs as the field) scaled into the
    sample box."""

    def __init__(self, entry) -> None:
        super().__init__(pg.PlotCurveItem())  # placeholder; we paint ourselves
        self._entry = entry

    def paint(self, p, *_args) -> None:
        from PySide6.QtCore import QPointF  # noqa: PLC0415

        from ...core._geometry import arrow_key_points  # noqa: PLC0415

        e = self._entry
        shaft, head = arrow_key_points(e.head_scale)
        w, h = self.width() or 20.0, self.height() or 20.0
        pad, mid = 2.0, h / 2.0
        sx = w - 2.0 * pad  # unit x-span → sample box width

        def pt(xy):
            return QPointF(pad + xy[0] * sx, mid - xy[1] * sx)

        p.setRenderHint(p.RenderHint.Antialiasing)
        p.setPen(pg.mkPen(e.swatch.qt(), width=max(e.line_width, 1.0)))
        p.drawPolyline([pt(q) for q in shaft])
        p.drawPolyline([pt(q) for q in head])


def _add_swatch(lg, label, color) -> None:
    swatch = pg.ScatterPlotItem([0], [0], brush=color.qt(), pen=None, size=10, symbol="s")
    lg.addItem(swatch, label)


def _add_colorbar(plot, legend, theme) -> None:
    """A true gradient colorbar for a continuous linear legend, replacing any prior
    one (re-aggregation refresh, C3). Inserted at the PlotItem-layout slot
    `ColorBarItem.setImageItem(insert_in=...)` uses — after the right axis — so it
    never collides with neighboring plots in a grid."""
    prev = getattr(plot, "_qtviz_cbar", None)
    if prev is not None:
        plot.layout.removeItem(prev)
        plot._qtviz_cbar = None
    ramp = legend.ramp
    if not ramp:
        return
    colors = np.array([[int(round(v * 255)) for v in c.rgba] for c in ramp], dtype=np.ubyte)
    cmap = pg.ColorMap(np.linspace(0.0, 1.0, len(ramp)), colors)
    bar = pg.ColorBarItem(values=(legend.vmin, legend.vmax), colorMap=cmap,
                          interactive=False, width=15, label=legend.title or "")
    plot.layout.addItem(bar, 2, 5)
    plot.layout.setColumnFixedWidth(4, 5)  # breathing room from the right axis
    plot._qtviz_cbar = bar
