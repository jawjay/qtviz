"""Color encoding — map a data column to per-element colors + a `Legend`.

One mapping rule, shared by the native renderers (per-point colors for a
`color_by` channel) and conceptually by the Datashader path (same palette → color
key / ramp), so a column colors the same way however it is drawn. Pure and
Qt-free; the renderers translate `Color`/`Legend` to their native widgets.

- A **categorical** column (non-numeric, or `kind="categorical"`) maps each
  distinct value to a palette color → a key legend.
- A **continuous** column maps the normalized value through a continuous palette
  (a 256-entry LUT for speed) → a colorbar legend with `vmin`/`vmax`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from .color import Color
from .palette import Palette

_LUT_N = 256
_RAMP_STOPS = (0.0, 0.25, 0.5, 0.75, 1.0)


@dataclass(frozen=True)
class Legend:
    """Backend-agnostic description of a color legend. Backends render it."""

    kind: Literal["categorical", "continuous"]
    title: str | None = None
    entries: tuple[tuple[str, Color], ...] = ()   # categorical: (label, swatch)
    vmin: float = 0.0                              # continuous bounds
    vmax: float = 1.0
    ramp: tuple[Color, ...] = field(default_factory=tuple)  # continuous swatch stops
    linear: bool = True  # False → color↔value is non-linear (e.g. eq_hist density):
    #                      show endpoints only, no interior linear ticks ([D48])


@dataclass(frozen=True)
class LegendEntry:
    """One element's contribution to a multi-series legend — its `label` text and
    swatch color ([D60]: legend as a per-element contract, not a color-mapping
    side-effect). Produced by `Element.legend_entry()`; an Overlay aggregates its
    children's entries into one legend.

    `glyph` picks the sample shape: `"swatch"` (default) is a color square;
    `"arrow"` ([D112], the Quiver reference key) draws the core unit-arrow
    sample (`_geometry.arrow_key_points`) with `line_width`/`head_scale`,
    where the backend's legend can draw custom samples (Plotly falls back to
    its own line sample)."""

    label: str
    swatch: Color
    glyph: str = "swatch"
    line_width: float = 1.5
    head_scale: float = 1.0


def is_categorical(values) -> bool:
    """A column is categorical unless it is a plain numeric dtype (int/float/
    complex). Booleans and strings/objects are treated as categories."""
    return np.asarray(values).dtype.kind not in "iufc"


def map_colors(
    values,
    *,
    palette: Palette,
    continuous_palette: Palette | None = None,
    kind: Literal["auto", "categorical", "continuous"] = "auto",
    vmin: float | None = None,
    vmax: float | None = None,
    title: str | None = None,
    norm: Literal["linear", "log"] = "linear",
) -> tuple[np.ndarray, Legend]:
    """`values` → `(rgba, legend)` where rgba is `(N, 4)` float in [0, 1].

    `palette` colors categories; `continuous_palette` (default: `palette`) is the
    ramp for numeric columns. `kind="auto"` picks by dtype. `norm="log"` ([D71])
    normalizes through log10 — the emitted Legend is then `linear=False`
    (endpoints-only key, [D48]) with data-space bounds; non-positive values warn
    and map to the bottom of the ramp.
    """
    arr = np.asarray(values)
    categorical = is_categorical(arr) if kind == "auto" else kind == "categorical"
    if categorical:
        return _categorical(arr, palette, title)
    return _continuous(arr, continuous_palette or palette, vmin, vmax, title, norm)


def continuous_ramp(palette: Palette) -> tuple[Color, ...]:
    """The continuous ramp sampled at five stops — shared by the native colorbar and
    the Datashader raster legend so both show the same ramp."""
    return tuple(palette.at(t) for t in _RAMP_STOPS)


def category_swatches(categories, palette: Palette) -> list[Color]:
    """One color per category — `palette[i % n]` for the i-th category, in the order
    given. Shared source of truth so a category gets the *same* swatch whether it is
    drawn natively (`map_colors`) or as a Datashader color key (`shade_aggregate`).
    Callers pass categories in canonical order (`np.unique` / sorted) so the two
    paths agree."""
    return [palette[i % len(palette)] for i in range(len(categories))]


def _categorical(arr, palette: Palette, title) -> tuple[np.ndarray, Legend]:
    cats, codes = np.unique(arr, return_inverse=True)
    swatches = category_swatches(cats, palette)
    lut = np.array([c.rgba for c in swatches], dtype="float64")
    rgba = lut[codes] if len(cats) else np.empty((0, 4))
    entries = tuple((str(c), swatches[i]) for i, c in enumerate(cats))
    return rgba, Legend(kind="categorical", title=title, entries=entries)


def _continuous(arr, palette: Palette, vmin, vmax, title,
                norm: str = "linear") -> tuple[np.ndarray, Legend]:
    a = np.asarray(arr, dtype="float64")
    if norm == "log":
        from ._scales import logify  # noqa: PLC0415

        a = logify(a, True)  # non-positive → NaN + warn ([D59] policy)
    lo = float(np.nanmin(a)) if vmin is None else float(vmin)
    hi = float(np.nanmax(a)) if vmax is None else float(vmax)
    span = (hi - lo) or 1.0
    normed = np.nan_to_num(np.clip((a - lo) / span, 0.0, 1.0), nan=0.0)
    lut = np.array([palette.at(t / (_LUT_N - 1)).rgba for t in range(_LUT_N)], dtype="float64")
    rgba = lut[(normed * (_LUT_N - 1)).astype("int64")]
    if norm == "log":  # legend bounds back in data space; non-linear → endpoints-only
        legend = Legend(kind="continuous", title=title, vmin=10.0**lo, vmax=10.0**hi,
                        ramp=continuous_ramp(palette), linear=False)
    else:
        legend = Legend(kind="continuous", title=title, vmin=lo, vmax=hi,
                        ramp=continuous_ramp(palette))
    return rgba, legend


RASTER_NORMS = ("linear", "log", "power")


def normalize_values(values, *, norm: str = "linear", vmin=None, vmax=None,
                     gamma: float = 1.0):
    """Raster color normalization ([D105]), computed once in core so every
    backend colors identically: → `(normed [0,1] float64, lo, hi)`. NaN is
    preserved; under `log`, non-positive values become NaN (blank cells) with
    one warning — the masked-image convention."""
    a = np.asarray(values, dtype="float64")
    finite = a[np.isfinite(a)]
    if norm == "log":
        if np.any(finite <= 0):
            import warnings  # noqa: PLC0415

            from ..errors import QtvizWarning  # noqa: PLC0415

            warnings.warn("norm='log': non-positive values render blank",
                          QtvizWarning, stacklevel=2)
            a = np.where(a > 0, a, np.nan)
        finite = finite[finite > 0]
    lo = float(vmin) if vmin is not None else (float(finite.min()) if len(finite) else 0.0)
    hi = float(vmax) if vmax is not None else (float(finite.max()) if len(finite) else 1.0)
    span = (hi - lo) or 1.0
    if norm == "log":
        lspan = (np.log10(hi) - np.log10(lo)) or 1.0
        with np.errstate(divide="ignore", invalid="ignore"):
            normed = (np.log10(a) - np.log10(lo)) / lspan
    elif norm == "power":
        normed = np.clip((a - lo) / span, 0.0, 1.0) ** gamma
    else:
        normed = (a - lo) / span
    return np.clip(normed, 0.0, 1.0), lo, hi


def denormalize(t: float, lo: float, hi: float, norm: str = "linear",
                gamma: float = 1.0) -> float:
    """The inverse of `normalize_values` for one tick position in [0, 1] —
    colorbar ticks label true data values."""
    if norm == "log":
        return float(10.0 ** (np.log10(lo) + t * (np.log10(hi) - np.log10(lo))))
    if norm == "power":
        return float(lo + (t ** (1.0 / gamma)) * (hi - lo))
    return float(lo + t * (hi - lo))


def norm_engaged(element) -> bool:
    """Whether the [D105] norm surface is in use — legends/limits only then,
    so pre-existing plain rasters keep their exact look."""
    return (getattr(element, "norm", "linear") != "linear"
            or getattr(element, "vmin", None) is not None
            or getattr(element, "vmax", None) is not None)
