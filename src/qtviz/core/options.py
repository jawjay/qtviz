"""Options containers (spec §2.2, §2.3).

`Options` is small and universal. Per-element styling lives on the Element
subclass, not here. `OverlayOptions` / `LayoutOptions` carry the
shared-surface concerns for the two composition operators.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ._immutable import Immutable
from .color import ColorSpec
from .palette import Palette


class Options(Immutable):
    """Universal per-Element style options: `color`, `alpha`, `palette`, `label`."""

    def __init__(
        self,
        *,
        color: ColorSpec | None = None,
        alpha: float | None = None,
        palette: Palette | None = None,
        label: str | None = None,
    ) -> None:
        self.color = color
        self.alpha = alpha
        self.palette = palette
        self.label = label
        if alpha is not None and not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self._freeze()


class OverlayOptions(Immutable):
    """Shared-surface options for an `Overlay`: title, axis labels, legend, background."""

    def __init__(
        self,
        *,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        legend: bool = True,
        background: ColorSpec | None = None,
    ) -> None:
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.legend = legend
        self.background = background
        self._freeze()


def _as_pairs(m) -> tuple | None:
    if m is None:
        return None
    items = m.items() if isinstance(m, Mapping) else m
    return tuple((int(k), str(v)) for k, v in items)


class LayoutOptions(Immutable):
    """Arrangement options for a `Layout`: rows/cols, spacing, axis linking
    (`link_x`/`link_y`), and tab/dock labels."""

    def __init__(
        self,
        *,
        rows: int | None = None,
        cols: int | None = None,
        spacing: int = 6,
        link_x: bool = False,
        link_y: bool = False,
        tab_labels: Sequence[str] | None = None,
        dock_areas: Mapping[int, str] | Sequence[tuple] | None = None,
        title: str | None = None,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.spacing = spacing
        self.link_x = link_x
        self.link_y = link_y
        self.tab_labels = tuple(tab_labels) if tab_labels is not None else None
        self.dock_areas = _as_pairs(dock_areas)
        self.title = title
        self._freeze()
