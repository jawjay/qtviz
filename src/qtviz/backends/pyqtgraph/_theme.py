"""Apply a qtviz Theme to a pyqtgraph surface (spec §2.13, §4.1)."""

from __future__ import annotations


def apply_theme(widget, theme) -> None:
    widget.setBackground(theme.background.qt())


def style_plot(plot, theme) -> None:
    pen = theme.foreground.qt()
    for axis in ("left", "bottom", "top", "right"):
        ax = plot.getAxis(axis)
        ax.setPen(pen)
        ax.setTextPen(pen)
    plot.showGrid(x=True, y=True, alpha=0.25)
