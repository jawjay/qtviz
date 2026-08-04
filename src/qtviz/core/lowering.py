"""Lowering — Element → Marks ([D122], `design/2.0-mark-ir-and-surface.md`).

`Element.lower(ctx)` turns a *resolved* element into a `Lowered`: the marks a
backend draws, the element's legend contribution ([D60] — routed through
`legend_entry()`, never re-derived), and optional brush-registration
coordinates. It runs inside `backend.render()` / `handle.update()` — never per
frame; the [D77] streaming fast path does not pass through here.

The context is deliberately minimal: no scales (marks are linear data space,
[D121]), no viewport, no widget — lowering is pure and headless-testable
(tier 1). A backend's registered native renderer wins over lowering (the
fast-path override), so `lower()` existing on an element changes nothing until
a backend has no native renderer for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .color import Color, ColorSpec
from .marks import Mark
from .theme import Theme


@dataclass(frozen=True)
class LowerContext:
    theme: Theme
    series_index: int = 0  # palette slot on this surface (`series_index_map`)
    show_legend: bool = True


@dataclass(frozen=True, eq=False)
class Lowered:
    """One element's contribution to its surface. `legend` is a
    `LegendEntry | Legend | None`; `select_xy` registers the coordinates a
    brush selects against ([D124] — replaces isinstance tuples in backend
    event wiring). Adapters gate legend drawing on `ctx.show_legend`;
    lowering always emits it so the [D123] perturbation guard sees `label=`
    survive."""

    marks: tuple[Mark, ...]
    legend: Any = None
    select_xy: tuple[np.ndarray, np.ndarray] | None = None


def resolve_color(spec: ColorSpec | None, theme: Theme, index: int = 0) -> Color:
    """The default-color rule every backend re-implements today (`_color` in
    each `_renderers.py`), in one place: an explicit spec wins; otherwise the
    element's palette slot."""
    if spec is None:
        return theme.palette[index % len(theme.palette)]
    return Color(spec)


def resolve_ref_color(spec: ColorSpec | None, theme: Theme) -> Color:
    """The annotation default ([D70]): the theme *foreground* — a reference is
    chrome, not a series, so it must never look like palette data."""
    return Color(spec) if spec is not None else theme.foreground
