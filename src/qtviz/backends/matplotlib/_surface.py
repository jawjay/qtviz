"""Apply shared-surface options to a matplotlib Axes (axis-surface seam, Phase A).

The semantic sibling of `_theme.apply_theme_ax`: theme sets the axis *colors*,
this sets the *text* declared on the surface (`OverlayOptions.title` / `x_label`
/ `y_label`). Scales / limits / tick-formatting land in later phases — see
`design/axis-surface-feasibility.md`.
"""

from __future__ import annotations


def apply_surface(ax, surf, theme) -> None:
    fg = theme.foreground.mpl()
    if surf.title:
        ax.set_title(surf.title, color=fg, fontsize=theme.title_size)
    if surf.x_label:
        ax.set_xlabel(surf.x_label, color=fg, fontsize=theme.font_size)
    if surf.y_label:
        ax.set_ylabel(surf.y_label, color=fg, fontsize=theme.font_size)
