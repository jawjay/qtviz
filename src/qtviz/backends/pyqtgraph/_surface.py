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


class _Y2Host:
    """PlotItem look-alike handed to renderers for y2 children ([D88]): items
    land in the twin ViewBox; axis/legend chrome still reaches the real plot."""

    def __init__(self, plot, vb2) -> None:
        self._plot, self._vb2 = plot, vb2

    def addItem(self, item, *args, **kwargs) -> None:
        self._vb2.addItem(item)

    def getViewBox(self):
        return self._vb2

    def __getattr__(self, name):
        return getattr(self._plot, name)


def make_y2(plot, vb, spec, theme, x_scale: str, y2_scale: str):
    """Build the twin right-hand ViewBox ([D88]): x-linked to the primary,
    driven by the right AxisItem, geometry-synced on resize. Emits no range
    events and takes no brush — the surface's events stay primary-axes."""
    import pyqtgraph as pg  # noqa: PLC0415

    vb2 = pg.ViewBox(enableMenu=False)
    x_log, y2_log = x_scale == "log", y2_scale == "log"
    vb2.x_log, vb2.y_log = x_log, y2_log
    # R1 for pick/hover coordinate emission (wire_scatter reads these):
    vb2._to_data_x = (lambda v: 10.0 ** v) if x_log else float
    vb2._to_data_y = (lambda v: 10.0 ** v) if y2_log else float
    plot.scene().addItem(vb2)
    plot.showAxis("right")
    right = plot.getAxis("right")
    right.linkToView(vb2)
    vb2.setXLink(vb)

    def _sync(*_a) -> None:
        vb2.setGeometry(vb.sceneBoundingRect())

    vb.sigResized.connect(_sync)
    _sync()
    _apply_axis(plot, vb2, "y", "right", spec, y2_scale, theme.foreground.hex())
    return vb2


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
