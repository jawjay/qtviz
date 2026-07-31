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


def _time_formatter(ax, axis: str):
    """Calendar labels for a time axis ([D94]/[D104]): values are epoch
    seconds; the strftime spec is the one `time_ticks` chose for the visible
    span, so labels and tick positions always agree."""
    from matplotlib.ticker import FuncFormatter  # noqa: PLC0415

    from ...core._time import format_time, time_ticks  # noqa: PLC0415

    limits = ax.get_xlim if axis == "x" else ax.get_ylim

    def fmt(v, _pos) -> str:
        lo, hi = limits()
        return format_time(v, time_ticks(lo, hi)[1])

    return FuncFormatter(fmt)


def _time_locator():
    """Calendar-aligned major ticks from the shared core ladder ([D104]) —
    month/day/hour boundaries instead of MaxNLocator's arbitrary seconds."""
    from matplotlib.ticker import Locator  # noqa: PLC0415

    from ...core._time import time_ticks  # noqa: PLC0415

    class _CalendarLocator(Locator):
        def __call__(self):
            lo, hi = self.axis.get_view_interval()
            return self.tick_values(lo, hi)

        def tick_values(self, vmin, vmax):
            return list(time_ticks(float(vmin), float(vmax))[0])

    return _CalendarLocator()


def _apply_ticks(ax, axis: str, spec) -> None:
    """Explicit ticks/labels ([D101]), minor ticks and label rotation ([D103])
    for one axis. Explicit ticks pin a FixedLocator (labels optional — without
    them the active formatter still applies)."""
    axobj = ax.xaxis if axis == "x" else ax.yaxis
    if spec.ticks is not None:
        setter = ax.set_xticks if axis == "x" else ax.set_yticks
        setter(list(spec.ticks),
               labels=list(spec.tick_labels) if spec.tick_labels is not None else None)
    if spec.minor:
        from matplotlib.ticker import AutoMinorLocator  # noqa: PLC0415

        axobj.set_minor_locator(AutoMinorLocator())
    if spec.tick_rotation:
        ax.tick_params(axis=axis, labelrotation=spec.tick_rotation)


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
    if x_scale in ("log", "symlog"):  # "time" stays linear (epoch seconds, [D94])
        ax.set_xscale(x_scale)
    if y_scale in ("log", "symlog"):
        ax.set_yscale(y_scale)
    if x_scale == "time":
        if surf.x.ticks is None:
            ax.xaxis.set_major_locator(_time_locator())
        if surf.x.tick_format == "auto":
            ax.xaxis.set_major_formatter(_time_formatter(ax, "x"))
    if y_scale == "time":
        if surf.y.ticks is None:
            ax.yaxis.set_major_locator(_time_locator())
        if surf.y.tick_format == "auto":
            ax.yaxis.set_major_formatter(_time_formatter(ax, "y"))
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
    _apply_ticks(ax, "x", surf.x)
    _apply_ticks(ax, "y", surf.y)


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
    if y2_scale in ("log", "symlog"):  # "time" stays linear ([D94])
        ax2.set_yscale(y2_scale)
    if y2_scale == "time":
        if spec.ticks is None:
            ax2.yaxis.set_major_locator(_time_locator())
        if spec.tick_format == "auto":
            ax2.yaxis.set_major_formatter(_time_formatter(ax2, "y"))
    if spec.lim is not None:
        ax2.set_ylim(*spec.lim)
    if spec.invert:
        ax2.invert_yaxis()
    if spec.tick_format != "auto":
        ax2.yaxis.set_major_formatter(_tick_formatter(spec.tick_format))
    _apply_ticks(ax2, "y", spec)
