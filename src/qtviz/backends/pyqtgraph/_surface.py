"""Apply shared-surface options to a pyqtgraph PlotItem (axis-surface seam, Phase A).

The semantic sibling of `_theme.style_plot`: theme sets the axis *colors*, this
sets the *text* declared on the surface (`OverlayOptions.title` / `x_label` /
`y_label`). Scales / limits / tick-formatting land in later phases — see
`design/axis-surface-feasibility.md`.
"""

from __future__ import annotations


def apply_surface(plot, surf, theme) -> None:
    color = theme.foreground.hex()
    if surf.title:
        plot.setTitle(surf.title, color=color, size=f"{theme.title_size}pt")
    if surf.x_label:
        plot.setLabel("bottom", surf.x_label, color=color)
    if surf.y_label:
        plot.setLabel("left", surf.y_label, color=color)
