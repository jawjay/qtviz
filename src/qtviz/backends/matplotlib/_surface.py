"""Apply shared-surface options to a matplotlib Axes (axis-surface seam).

The semantic sibling of `_theme.apply_theme_ax`: theme sets the axis *colors*, this
sets what the surface *declares* — title / labels (Phase A) and, now, declarative
`lim` / `invert` / `aspect` and the capability-gated scale (0.3 increment 1; log
*rendering* lands in increment 2 — matplotlib needs no R1, but the scale is gated here
uniformly). See `design/axis-surface-feasibility.md`.
"""

from __future__ import annotations

from ...core.compose import resolve_scale


def apply_surface(ax, surf, theme, scales) -> None:
    fg = theme.foreground.mpl()
    if surf.title:
        ax.set_title(surf.title, color=fg, fontsize=theme.title_size)
    if surf.x.label:
        ax.set_xlabel(surf.x.label, color=fg, fontsize=theme.font_size)
    if surf.y.label:
        ax.set_ylabel(surf.y.label, color=fg, fontsize=theme.font_size)
    resolve_scale(surf.x.scale, scales, axis="x", backend="matplotlib")  # warn-gate
    resolve_scale(surf.y.scale, scales, axis="y", backend="matplotlib")
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
