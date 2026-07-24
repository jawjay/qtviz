"""Apply shared-surface options to a matplotlib Axes (axis-surface seam).

The semantic sibling of `_theme.apply_theme_ax`: theme sets the axis *colors*, this
sets what the surface *declares* — title / labels (Phase A), declarative `lim` /
`invert` / `aspect` (0.3 increment 1), and the axis scale (increment 2). matplotlib
transforms the data itself under `set_xscale` and keeps `get_xlim()` in data space,
so it needs **no** R1 coordinate work (feasibility §10.2). The caller resolves the
effective scales via `core.compose.effective_scales`.
"""

from __future__ import annotations


def apply_surface(ax, surf, theme, x_scale: str, y_scale: str) -> None:
    fg = theme.foreground.mpl()
    if surf.title:
        ax.set_title(surf.title, color=fg, fontsize=theme.title_size)
    if surf.x.label:
        ax.set_xlabel(surf.x.label, color=fg, fontsize=theme.font_size)
    if surf.y.label:
        ax.set_ylabel(surf.y.label, color=fg, fontsize=theme.font_size)
    if x_scale != "linear":
        ax.set_xscale(x_scale)
    if y_scale != "linear":
        ax.set_yscale(y_scale)
    if surf.x.lim is not None:
        ax.set_xlim(*surf.x.lim)
    if surf.y.lim is not None:
        ax.set_ylim(*surf.y.lim)
    if surf.x.invert:
        ax.invert_xaxis()
    if surf.y.invert:
        ax.invert_yaxis()
    if surf.aspect is not None:
        ax.set_aspect(surf.aspect)
