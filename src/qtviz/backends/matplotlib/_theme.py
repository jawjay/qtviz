"""Apply a qtviz Theme to a matplotlib Figure/Axes (spec §2.13, §4.2)."""

from __future__ import annotations


def apply_theme_fig(fig, theme) -> None:
    fig.patch.set_facecolor(theme.background.mpl())


def apply_theme_ax(ax, theme) -> None:
    fg = theme.foreground.mpl()
    ax.set_facecolor(theme.background.mpl())
    for spine in ax.spines.values():
        spine.set_color(fg)
    ax.tick_params(colors=fg)
    ax.xaxis.label.set_color(fg)
    ax.yaxis.label.set_color(fg)
    ax.title.set_color(fg)
    ax.grid(True, color=theme.grid.mpl(), alpha=0.5)
