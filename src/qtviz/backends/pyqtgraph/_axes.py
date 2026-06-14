"""Linked axes for single-backend grid layouts (milestone M4, spec §4.1).

Cross-backend / mixed-pane linking is out of scope until the LayoutHost (M5).
"""

from __future__ import annotations


def link_axes(plots, *, link_x: bool, link_y: bool) -> None:
    if not plots:
        return
    base = plots[0].getViewBox()
    for plot in plots[1:]:
        vb = plot.getViewBox()
        if link_x:
            vb.setXLink(base)
        if link_y:
            vb.setYLink(base)
