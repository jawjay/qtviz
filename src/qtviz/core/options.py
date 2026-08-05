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


class _Unset:
    """Sentinel for `.opts()` field-wise merges — `None` must stay a
    real value (e.g. `background=None` clears)."""

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return "UNSET"


UNSET = _Unset()


def _as_axis(value) -> AxisSpec | None:
    """The shorthand: a bare string is the axis label."""
    if value is None or isinstance(value, AxisSpec):
        return value
    if isinstance(value, str):
        return AxisSpec(label=value)
    raise ValidationError(f"axis config must be a label string or AxisSpec, got {value!r}")

# The axis-scale vocabulary (semantic, backend-agnostic; feasibility §2.1). A backend
# renders the subset it declares in `Capabilities.scales`; the rest warn-and-degrade
# to linear ([D59]). `time` is reserved (gated on the data layer carrying datetime).
_SCALES = ("linear", "log", "symlog", "time")


class AxisSpec(Immutable):
    """Per-axis surface configuration — label, scale, limits, ticks.

    `scale` (`linear|log|symlog|time`), declarative `lim`, `invert`;
    `tick_format` is `"auto"`, `"eng"`, a Python format-spec
    (`".2f"`, `",d"`, `".0%"`), a strftime pattern, or a one-field template
    (`"${:,.0f}"`, `"{:.0f} ms"`); explicit `ticks`/`tick_labels` pin the
    positions/labels; `minor=True` requests minor ticks and
    `tick_rotation` rotates the labels. All positions are data space
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
    plus the twin `y2`, ), `aspect`, legend toggle + position, background,
    grid toggle.

    `x`/`y`/`y2` take an `AxisSpec` or — the shorthand — a bare string
    meaning the axis label; `AxisSpec.label` is the one canonical home. `y2`
    configures the right-hand axis that appears when any series element sets
    `axis="y2"` — it is ignored when none does. `legend` is one union field
: `True`/`"auto"` places automatically, `"right"`/`"top"` place
    explicitly, `False`/`"none"` hides everything."""

    def __init__(
        self,
        *,
        title: str | None = None,
        x: AxisSpec | str | None = None,
        y: AxisSpec | str | None = None,
        y2: AxisSpec | str | None = None,
        aspect: float | None = None,
        legend: bool | str = "auto",
        background: ColorSpec | None = None,
        grid: bool = True,
    ) -> None:
        if not isinstance(legend, bool) and legend not in _LEGEND_POSITIONS:
            raise ValidationError(
                f"legend must be a bool or one of {_LEGEND_POSITIONS}, got {legend!r}"
            )
        self.title = title
        self.x = _as_axis(x) or AxisSpec()
        self.y = _as_axis(y) or AxisSpec()
        self.y2 = _as_axis(y2)
        self.aspect = float(aspect) if aspect is not None else None
        self.legend = legend
        self.background = background
        self.grid = bool(grid)
        self._freeze()

    @property
    def legend_enabled(self) -> bool:
        """The one switch backends consult: `legend=False`/`"none"` hides every
        legend on the surface (aggregated *and* color-mapping)."""
        return self.legend not in (False, "none")

    @property
    def legend_position(self) -> str:
        """The placement backends translate: `"auto"` unless placed explicitly."""
        return self.legend if self.legend in ("right", "top", "none") else "auto"


def _as_pairs(m) -> tuple | None:
    if m is None:
        return None
    items = m.items() if isinstance(m, Mapping) else m
    return tuple((int(k), str(v)) for k, v in items)


def _as_link(v, name: str):
    """[D146] axis-link vocabulary: `False` (none), `True` (all panes),
    `"col"`/`"row"` (within each grid column/row; a spanning pane joins — and
    transitively merges — every group it covers)."""
    if isinstance(v, bool) or v in ("col", "row"):
        return v
    raise ValidationError(f"{name} must be a bool, 'col', or 'row', got {v!r}")


def _as_ratios(v, name: str) -> tuple[float, ...] | None:
    if v is None:
        return None
    out = tuple(float(x) for x in v)
    if not out or any(x <= 0 for x in out):
        raise ValidationError(f"{name} must be positive numbers, got {v!r}")
    return out


class LayoutOptions(Immutable):
    """Arrangement options for a `Layout`: rows/cols, spacing, axis linking
    (`link_x`/`link_y` — `True` links all panes, `"col"`/`"row"` link within
    each grid column/row, [D146]), tab/dock labels, relative column/row sizes
    (`width_ratios`/`height_ratios`, ), and a container `title`
    (the figure suptitle)."""

    def __init__(
        self,
        *,
        rows: int | None = None,
        cols: int | None = None,
        spacing: int = 6,
        link_x: bool | str = False,
        link_y: bool | str = False,
        tab_labels: Sequence[str] | None = None,
        dock_areas: Mapping[int, str] | Sequence[tuple] | None = None,
        title: str | None = None,
        width_ratios: Sequence[float] | None = None,
        height_ratios: Sequence[float] | None = None,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.spacing = spacing
        self.link_x = _as_link(link_x, "link_x")
        self.link_y = _as_link(link_y, "link_y")
        self.tab_labels = tuple(tab_labels) if tab_labels is not None else None
        self.dock_areas = _as_pairs(dock_areas)
        self.title = title
        self.width_ratios = _as_ratios(width_ratios, "width_ratios")
        self.height_ratios = _as_ratios(height_ratios, "height_ratios")
        self._freeze()
