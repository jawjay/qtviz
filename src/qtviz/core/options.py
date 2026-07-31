"""Options containers (spec §2.3).

Per-element styling lives on the Element subclass. `OverlayOptions` /
`LayoutOptions` carry the shared-surface concerns for the two composition
operators. (`Options` — spec §2.2, never wired — was deprecated in 0.2 and
removed here, as `docs/stability.md` promised.)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..errors import ValidationError
from ._immutable import Immutable
from .color import ColorSpec

# The axis-scale vocabulary (semantic, backend-agnostic; feasibility §2.1). A backend
# renders the subset it declares in `Capabilities.scales`; the rest warn-and-degrade
# to linear ([D59]). `time` is reserved (gated on the data layer carrying datetime).
_SCALES = ("linear", "log", "symlog", "time")


class AxisSpec(Immutable):
    """Per-axis surface config (axis-surface seam; feasibility §2.1, [D59]).

    `scale` (`linear|log|symlog|time`), declarative `lim`, `invert`;
    `tick_format` ([D86]/[D102]) is `"auto"`, `"eng"`, a Python format-spec
    (`".2f"`, `",d"`, `".0%"`), a strftime pattern, or a one-field template
    (`"${:,.0f}"`, `"{:.0f} ms"`); explicit `ticks`/`tick_labels` pin the
    positions/labels ([D101]); `minor=True` requests minor ticks and
    `tick_rotation` rotates the labels ([D103]). All positions are data space
    (R1). A backend that can't render the requested `scale` warns and falls
    back to linear."""

    def __init__(
        self,
        *,
        label: str | None = None,
        scale: str = "linear",
        lim: tuple[float, float] | None = None,
        invert: bool = False,
        tick_format: str = "auto",
        ticks: tuple[float, ...] | list[float] | None = None,
        tick_labels: tuple[str, ...] | list[str] | None = None,
        minor: bool = False,
        tick_rotation: float = 0.0,
    ) -> None:
        from ._ticks import validate_tick_format  # noqa: PLC0415 — avoid a cycle

        if scale not in _SCALES:
            raise ValidationError(f"scale must be one of {_SCALES}, got {scale!r}")
        if lim is not None and len(tuple(lim)) != 2:
            raise ValidationError(f"lim must be a (lo, hi) pair, got {lim!r}")
        validate_tick_format(tick_format)
        if tick_labels is not None and ticks is None:
            raise ValidationError("tick_labels requires ticks")
        if ticks is not None:
            ticks = tuple(float(v) for v in ticks)
            if tick_labels is not None:
                tick_labels = tuple(str(v) for v in tick_labels)
                if len(tick_labels) != len(ticks):
                    raise ValidationError(
                        f"tick_labels ({len(tick_labels)}) must match ticks "
                        f"({len(ticks)})")
        self.label = label
        self.scale = scale
        self.lim = (float(lim[0]), float(lim[1])) if lim is not None else None
        self.invert = bool(invert)
        self.tick_format = tick_format
        self.ticks = ticks
        self.tick_labels = tick_labels
        self.minor = bool(minor)
        self.tick_rotation = float(tick_rotation)
        self._freeze()


# Where a surface's legend goes ([D60]); translated per backend, `none` hides it.
_LEGEND_POSITIONS = ("auto", "right", "top", "none")


class OverlayOptions(Immutable):
    """Shared-surface options for an `Overlay`: title, per-axis `AxisSpec` (`x`/`y`,
    plus the twin `y2`, [D88]), `aspect`, legend toggle + position, background,
    grid toggle ([D87]).

    `x_label`/`y_label` are conveniences that populate `x.label`/`y.label` (so the
    canonical axis config has one home, `AxisSpec`); they remain readable as
    properties for back-compat. `y2` configures the right-hand axis that appears
    when any series element sets `axis="y2"` — it is ignored when none does."""

    def __init__(
        self,
        *,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        x: AxisSpec | None = None,
        y: AxisSpec | None = None,
        y2: AxisSpec | None = None,
        aspect: float | None = None,
        legend: bool = True,
        legend_position: str = "auto",
        background: ColorSpec | None = None,
        grid: bool = True,
    ) -> None:
        if legend_position not in _LEGEND_POSITIONS:
            raise ValidationError(
                f"legend_position must be one of {_LEGEND_POSITIONS}, got {legend_position!r}"
            )
        self.title = title
        self.x = x if x is not None else AxisSpec(label=x_label)
        self.y = y if y is not None else AxisSpec(label=y_label)
        self.y2 = y2
        self.aspect = float(aspect) if aspect is not None else None
        self.legend = legend
        self.legend_position = legend_position
        self.background = background
        self.grid = bool(grid)
        self._freeze()

    @property
    def legend_enabled(self) -> bool:
        """The one switch backends consult: `legend=False` or `position="none"`
        both hide every legend on the surface (aggregated *and* color-mapping)."""
        return self.legend and self.legend_position != "none"

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
