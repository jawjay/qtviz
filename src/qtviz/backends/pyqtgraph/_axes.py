"""Linked axes for single-backend grid layouts (milestone M4, spec §4.1;
[D146] structured sharing).

Groups come from `core.compose.link_groups` — the same cells that decide grid
shape — so `True` links all panes and `"col"`/`"row"` link within each grid
column/row (spanning panes merge groups, the `subplot_mosaic` rule). Members
link natively (`setXLink`) to their group's first pane. Cross-backend /
mixed-pane linking is the LayoutHost's `_LinkController` ([D151]).
"""

from __future__ import annotations


def link_axes(plots, *, cells, link_x, link_y) -> None:
    from ...core.compose import link_groups  # noqa: PLC0415

    for mode, setter in ((link_x, "setXLink"), (link_y, "setYLink")):
        for group in link_groups(cells, len(plots), mode):
            base = plots[group[0]].getViewBox()
            for i in group[1:]:
                getattr(plots[i].getViewBox(), setter)(base)
