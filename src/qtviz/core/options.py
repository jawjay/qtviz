"""Options containers (spec §2.2, §2.3).

`Options` is small and universal. Per-element styling lives on the Element
subclass, not here. `OverlayOptions` / `LayoutOptions` carry the
shared-surface concerns for the two composition operators.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence

from ..errors import ValidationError
from ._immutable import Immutable
from ._validate import check_alpha
from .color import ColorSpec
from .palette import Palette

# The axis-scale vocabulary (semantic, backend-agnostic; feasibility §2.1). A backend
# renders the subset it declares in `Capabilities.scales`; the rest warn-and-degrade
# to linear ([D59]). `time` is reserved (gated on the data layer carrying datetime).
_SCALES = ("linear", "log", "symlog", "time")


class Options(Immutable):
    """Deprecated, unused universal style options ([D51] / weakness-root-causes R4).

    Specified in §2.2 but never wired: no Element accepts an `options=` argument and
    no renderer reads it — per-element styling lives on the Element subclass instead
    (`Scatter(color=..., alpha=...)`). Kept importable through 1.0 with a
    `DeprecationWarning` (non-breaking, honor-or-warn), removed thereafter.
    `OverlayOptions` / `LayoutOptions` are live and unaffected."""

    def __init__(
        self,
        *,
        color: ColorSpec | None = None,
        alpha: float | None = None,
        palette: Palette | None = None,
        label: str | None = None,
    ) -> None:
        warnings.warn(
            "qtviz.Options is unused and deprecated; set styling via per-element "
            "fields (e.g. Scatter(color=..., alpha=...)). It will be removed after 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.color = color
        self.alpha = alpha
        self.palette = palette
        self.label = label
        check_alpha(alpha, who="Options")
        self._freeze()


class AxisSpec(Immutable):
    """Per-axis surface config (axis-surface seam; feasibility §2.1, [D59]).

    `scale` (`linear|log|symlog|time`), declarative `lim`, and `invert` land in 0.3;
    `tick_format` is reserved for a later phase (honored as ``"auto"`` for now). A
    backend that can't render the requested `scale` warns and falls back to linear."""

    def __init__(
        self,
        *,
        label: str | None = None,
        scale: str = "linear",
        lim: tuple[float, float] | None = None,
        invert: bool = False,
        tick_format: str = "auto",
    ) -> None:
        if scale not in _SCALES:
            raise ValidationError(f"scale must be one of {_SCALES}, got {scale!r}")
        if lim is not None and len(tuple(lim)) != 2:
            raise ValidationError(f"lim must be a (lo, hi) pair, got {lim!r}")
        self.label = label
        self.scale = scale
        self.lim = (float(lim[0]), float(lim[1])) if lim is not None else None
        self.invert = bool(invert)
        self.tick_format = tick_format
        self._freeze()


class OverlayOptions(Immutable):
    """Shared-surface options for an `Overlay`: title, per-axis `AxisSpec` (`x`/`y`),
    `aspect`, legend toggle, background.

    `x_label`/`y_label` are conveniences that populate `x.label`/`y.label` (so the
    canonical axis config has one home, `AxisSpec`); they remain readable as
    properties for back-compat."""

    def __init__(
        self,
        *,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        x: AxisSpec | None = None,
        y: AxisSpec | None = None,
        aspect: float | None = None,
        legend: bool = True,
        background: ColorSpec | None = None,
    ) -> None:
        self.title = title
        self.x = x if x is not None else AxisSpec(label=x_label)
        self.y = y if y is not None else AxisSpec(label=y_label)
        self.aspect = float(aspect) if aspect is not None else None
        self.legend = legend
        self.background = background
        self._freeze()

    @property
    def x_label(self) -> str | None:
        return self.x.label

    @property
    def y_label(self) -> str | None:
        return self.y.label


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
