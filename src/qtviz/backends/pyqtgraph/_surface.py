"""Apply shared-surface options to a pyqtgraph PlotItem (axis-surface seam).

The semantic sibling of `_theme.style_plot`: theme sets the axis *colors*, this sets
what the surface *declares* — title / labels (Phase A), declarative `lim` / `invert` /
`aspect` (0.3 increment 1), the axis scale (increment 2), and a per-surface
`background` (plot area only — the widget chrome stays on the theme). Under log the ViewBox
lives in exponent space (Approach A: renderers pre-`log10` the data; the `AxisItem`
switches to log ticks only), so a data-space `lim` is transformed here. The caller
resolves the *effective* scales (capability gate + raster gate) via
`core.compose.effective_scales`. See `design/axis-surface-feasibility.md` §10.
"""

from __future__ import annotations

from ...core._scales import log_lim
from ...core._ticks import format_tick
from ...core.color import Color


def _tick_strings(spec: str, is_log: bool):
    """A `tickStrings` replacement for one AxisItem ([D86]). Under log the axis
    lives in exponent space (Approach A), so labels format 10**v — the R1 rule:
    users see data space."""

    def fmt(values, scale, _spacing) -> list[str]:
        return [format_tick((10.0 ** v) if is_log else v * scale, spec) for v in values]

    return fmt


def apply_surface(plot, surf, theme, x_scale: str, y_scale: str) -> None:
    color = theme.foreground.hex()
    if surf.title:
        plot.setTitle(surf.title, color=color, size=f"{theme.title_size}pt")
    vb = plot.getViewBox()
    if surf.background is not None:
        vb.setBackgroundColor(Color(surf.background).qt())  # plot area only
    _apply_axis(plot, vb, "x", "bottom", surf.x, x_scale, color)
    _apply_axis(plot, vb, "y", "left", surf.y, y_scale, color)
    if surf.aspect is not None:
        vb.setAspectLocked(True, surf.aspect)
    if not surf.grid:
        plot.showGrid(x=False, y=False)  # override the themed default ([D87])


def _apply_axis(plot, vb, axis: str, side: str, spec, eff_scale: str, color) -> None:
    if spec.label:
        plot.setLabel(side, spec.label, color=color)
    is_log = eff_scale == "log"
    if is_log:
        plot.getAxis(side).setLogMode(True)  # tick labels only; data is pre-log10'd
    if spec.tick_format != "auto":  # ([D86]) instance override shadows the method
        plot.getAxis(side).tickStrings = _tick_strings(spec.tick_format, is_log)
    lim = spec.lim
    if lim is not None and is_log:
        lim = log_lim(lim, axis=axis, backend="pyqtgraph")  # exponent space (or warn+skip)
    if lim is not None:
        (vb.setXRange if axis == "x" else vb.setYRange)(*lim, padding=0)
    if spec.invert:
        (vb.invertX if axis == "x" else vb.invertY)(True)
