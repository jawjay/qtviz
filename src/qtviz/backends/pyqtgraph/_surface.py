"""Apply shared-surface options to a pyqtgraph PlotItem (axis-surface seam).

The semantic sibling of `_theme.style_plot`: theme sets the axis *colors*, this sets
what the surface *declares* — title / labels (Phase A) and, now, declarative
`lim` / `invert` / `aspect` and the capability-gated scale (0.3 increment 1; the
`scale` value is *warned-and-gated* here, while log *rendering* + R1 coordinate
normalization land in increment 2). See `design/axis-surface-feasibility.md`.
"""

from __future__ import annotations

from ...core.compose import resolve_scale


def apply_surface(plot, surf, theme, scales) -> None:
    color = theme.foreground.hex()
    if surf.title:
        plot.setTitle(surf.title, color=color, size=f"{theme.title_size}pt")
    vb = plot.getViewBox()
    _apply_axis(plot, vb, "x", "bottom", surf.x, scales, color)
    _apply_axis(plot, vb, "y", "left", surf.y, scales, color)
    if surf.aspect is not None:
        vb.setAspectLocked(True, surf.aspect)


def _apply_axis(plot, vb, axis: str, side: str, spec, scales, color) -> None:
    if spec.label:
        plot.setLabel(side, spec.label, color=color)
    resolve_scale(spec.scale, scales, axis=axis, backend="pyqtgraph")  # warn-gate
    if spec.lim is not None:
        (vb.setXRange if axis == "x" else vb.setYRange)(*spec.lim, padding=0)
    if spec.invert:
        (vb.invertX if axis == "x" else vb.invertY)(True)
