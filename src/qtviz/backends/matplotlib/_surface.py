"""Apply shared-surface options to a matplotlib Axes (axis-surface seam).

The semantic sibling of `_theme.apply_theme_ax`: theme sets the axis *colors*, this
sets what the surface *declares* — title / labels (Phase A), declarative `lim` /
`invert` / `aspect` (0.3 increment 1), the axis scale (increment 2), and a
per-surface `background` (plot area only — the figure stays on the theme).
matplotlib transforms the data itself under `set_xscale` and keeps `get_xlim()` in
data space, so it needs **no** R1 coordinate work (feasibility §10.2). The caller
resolves the effective scales via `core.compose.effective_scales`.
"""

from __future__ import annotations

from ...core._ticks import format_tick
from ...core.color import Color


def _tick_formatter(spec: str):
    from matplotlib.ticker import FuncFormatter  # noqa: PLC0415

    return FuncFormatter(lambda v, _pos: format_tick(v, spec))


def apply_surface(ax, surf, theme, x_scale: str, y_scale: str) -> None:
    fg = theme.foreground.mpl()
    if surf.background is not None:
        ax.set_facecolor(Color(surf.background).mpl())
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
    if not surf.grid:
        ax.grid(False)  # override the themed default ([D87])
    if surf.x.tick_format != "auto":  # ([D86]); mpl passes data-space values
        ax.xaxis.set_major_formatter(_tick_formatter(surf.x.tick_format))
    if surf.y.tick_format != "auto":
        ax.yaxis.set_major_formatter(_tick_formatter(surf.y.tick_format))


def apply_y2(ax2, spec, theme, y2_scale: str) -> None:
    """Configure the twin right-hand axes ([D88]): themed like the primary but
    grid-less (two grids on one surface fight), carrying its own `AxisSpec`."""
    fg = theme.foreground.mpl()
    ax2.grid(False)
    ax2.tick_params(colors=fg)
    ax2.yaxis.label.set_color(fg)
    ax2.spines["right"].set_color(fg)
    if spec.label:
        ax2.set_ylabel(spec.label, color=fg, fontsize=theme.font_size)
    if y2_scale != "linear":
        ax2.set_yscale(y2_scale)
    if spec.lim is not None:
        ax2.set_ylim(*spec.lim)
    if spec.invert:
        ax2.invert_yaxis()
    if spec.tick_format != "auto":
        ax2.yaxis.set_major_formatter(_tick_formatter(spec.tick_format))
