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


def channel_title(accessor) -> str | None:
    """Legend title for a data-bound channel ([D129]): accessors are the full
    `str | Expression | Callable | ArrayLike` union, but only a column name —
    plain or a bare `col()` (duck-typed on `.name` to keep core import-light) —
    has a printable name. Derived/opaque accessors get no title rather than a
    repr dump."""
    if isinstance(accessor, str):
        return accessor
    name = getattr(accessor, "name", None)
    return name if isinstance(name, str) else None


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
    norm: str | Norm = "linear",
) -> tuple[np.ndarray, Legend]:
    """`values` → `(rgba, legend)` where rgba is `(N, 4)` float in [0, 1].

    `palette` colors categories; `continuous_palette` (default: `palette`) is the
    ramp for numeric columns. `kind="auto"` picks by dtype. `norm` is the shared
    normalization vocabulary (a name or a `Norm` spec) run through
    `normalize_values`, so a column colors exactly like a raster would; any
    non-linear norm emits a `linear=False` legend (endpoints-only key, [D48])
    with data-space bounds. Under `log`, non-positive values warn and map to
    the bottom of the ramp.
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
                norm: str | Norm = "linear") -> tuple[np.ndarray, Legend]:
    spec = norm if isinstance(norm, Norm) else Norm(norm)
    a = np.asarray(arr, dtype="float64")
    normed, lo, hi = normalize_values(
        a, norm=spec.kind, vmin=vmin, vmax=vmax,
        gamma=spec.gamma, linthresh=spec.linthresh, levels=spec.levels)
    normed = np.nan_to_num(normed, nan=0.0)  # blanks sit at the bottom of the ramp
    lut = np.array([palette.at(t / (_LUT_N - 1)).rgba for t in range(_LUT_N)], dtype="float64")
    rgba = lut[(normed * (_LUT_N - 1)).astype("int64")]
    # lo/hi are data-space; a non-linear color↔value relation → endpoints-only key
    legend = Legend(kind="continuous", title=title, vmin=lo, vmax=hi,
                    ramp=continuous_ramp(palette), linear=spec.kind == "linear")
    return rgba, legend


RASTER_NORMS = ("linear", "log", "power", "symlog", "boundary")


def _symlog_fwd(a, linthresh: float):
    """mpl's symlog transform (linscale=1, base 10), one numpy expression:
    linear within ±linthresh, logarithmic beyond — continuous at the seam."""
    with np.errstate(divide="ignore", invalid="ignore"):
        logged = np.sign(a) * linthresh * (1.0 + np.log10(np.abs(a) / linthresh))
    return np.where(np.abs(a) <= linthresh, a, logged)


def _symlog_inv(s: float, linthresh: float) -> float:
    if abs(s) <= linthresh:
        return float(s)
    return float(np.sign(s) * linthresh * 10.0 ** (abs(s) / linthresh - 1.0))


class Norm:
    """The one colormap-normalization spec, shared by every element that maps
    values to color (`Image`, `Heatmap`, `Mesh`, `Scatter.color_by`). The
    string shorthand (`norm="log"`) covers the 90% case; `Norm` carries only
    the transform's own parameters (`gamma` for `power`, `linthresh` for
    `symlog`, `levels` for `boundary`) — the value-range clamp is the
    separate `clim=`. A parameter set for a kind that ignores it raises:
    accept-then-ignore is the one sin this library refuses."""

    kind: str
    gamma: float
    linthresh: float
    levels: tuple[float, ...] | None

    __slots__ = ("kind", "gamma", "linthresh", "levels")

    def __init__(self, kind: str = "linear", *, gamma: float = 1.0,
                 linthresh: float = 1.0, levels=None) -> None:
        from ..errors import ValidationError  # noqa: PLC0415

        if kind not in RASTER_NORMS:
            raise ValidationError(f"Norm kind must be one of {RASTER_NORMS}, got {kind!r}")
        if float(gamma) <= 0:
            raise ValidationError(f"Norm gamma must be positive, got {gamma!r}")
        if float(gamma) != 1.0 and kind != "power":
            raise ValidationError("Norm: gamma requires kind='power'")
        if float(linthresh) <= 0:
            raise ValidationError(f"Norm linthresh must be positive, got {linthresh!r}")
        if float(linthresh) != 1.0 and kind != "symlog":
            raise ValidationError("Norm: linthresh requires kind='symlog'")
        if kind == "boundary":
            if levels is None or len(levels) < 2:
                raise ValidationError("Norm: kind='boundary' needs >= 2 ascending levels")
            lv = tuple(float(v) for v in levels)
            if any(b <= a for a, b in zip(lv, lv[1:], strict=False)):
                raise ValidationError(f"Norm levels must be ascending, got {list(lv)}")
        elif levels is not None:
            raise ValidationError("Norm: levels requires kind='boundary'")
        object.__setattr__(self, "kind", str(kind))
        object.__setattr__(self, "gamma", float(gamma))
        object.__setattr__(self, "linthresh", float(linthresh))
        object.__setattr__(self, "levels",
                           tuple(float(v) for v in levels) if levels is not None else None)

    def __setattr__(self, *_a) -> None:
        raise AttributeError("Norm is immutable")

    def _key(self):
        return (self.kind, self.gamma, self.linthresh, self.levels)

    def __eq__(self, other) -> bool:
        return isinstance(other, Norm) and self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __repr__(self) -> str:
        extras = []
        if self.gamma != 1.0:
            extras.append(f"gamma={self.gamma!r}")
        if self.linthresh != 1.0:
            extras.append(f"linthresh={self.linthresh!r}")
        if self.levels is not None:
            extras.append(f"levels={list(self.levels)!r}")
        inner = ", ".join([repr(self.kind), *extras])
        return f"Norm({inner})"


def normalize_values(values, *, norm: str = "linear", vmin=None, vmax=None,
                     gamma: float = 1.0, linthresh: float = 1.0, levels=None):
    """Raster color normalization ([D105]), computed once in core so every
    backend colors identically: → `(normed [0,1] float64, lo, hi)`. NaN is
    preserved; under `log`, non-positive values become NaN (blank cells) with
    one warning — the masked-image convention.

    [D114] tail: `symlog` is mpl's piecewise transform (linear within
    ±`linthresh`); `boundary` bins values into `len(levels)-1` discrete
    colors sampled evenly from the colormap (`searchsorted` forward), with
    `lo`/`hi` pinned to the outer levels."""
    a = np.asarray(values, dtype="float64")
    if norm == "boundary":
        lv = np.asarray(levels, dtype="float64")
        k = len(lv)
        idx = np.clip(np.searchsorted(lv, a, side="right") - 1, 0, k - 2)
        normed = np.where(np.isnan(a), np.nan, (idx + 0.5) / (k - 1))
        return normed, float(lv[0]), float(lv[-1])
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
    elif norm == "symlog":
        s_lo, s_hi = _symlog_fwd(np.array(lo), linthresh), _symlog_fwd(np.array(hi), linthresh)
        sspan = float(s_hi - s_lo) or 1.0
        normed = (_symlog_fwd(a, linthresh) - float(s_lo)) / sspan
    else:
        normed = (a - lo) / span
    return np.clip(normed, 0.0, 1.0), lo, hi


def denormalize(t: float, lo: float, hi: float, norm: str = "linear",
                gamma: float = 1.0, *, linthresh: float = 1.0, levels=None) -> float:
    """The inverse of `normalize_values` for one tick position in [0, 1] —
    colorbar ticks label true data values. `boundary` maps a position back to
    its bin's midpoint ([D114])."""
    if norm == "log":
        return float(10.0 ** (np.log10(lo) + t * (np.log10(hi) - np.log10(lo))))
    if norm == "power":
        return float(lo + (t ** (1.0 / gamma)) * (hi - lo))
    if norm == "symlog":
        s_lo = float(_symlog_fwd(np.array(lo), linthresh))
        s_hi = float(_symlog_fwd(np.array(hi), linthresh))
        return _symlog_inv(s_lo + t * (s_hi - s_lo), linthresh)
    if norm == "boundary":
        lv = np.asarray(levels, dtype="float64")
        i = int(np.clip(np.floor(t * (len(lv) - 1)), 0, len(lv) - 2))
        return float((lv[i] + lv[i + 1]) / 2.0)
    return float(lo + t * (hi - lo))


# ── heatmap cell labels ([D113]) ─────────────────────────────────────────────
@dataclass(frozen=True)
class CellLabel:
    """One heatmap cell's label ([D113]): grid indices, the cell-center
    position (numeric axes: the center value; categorical axes: the index
    position — the same convention the renderers' extents use), the formatted
    text, and the contrast-picked text color."""

    i: int
    j: int
    x: float
    y: float
    text: str
    color: Color


CELL_LABEL_MAX = 400  # ≈ matplotlib's practical annotated-heatmap limit

# Luminance threshold for flipping label text dark↔light; the constant was
# chosen by eye against the mpl annotated-heatmap reference figure.
_LABEL_LUMINANCE = 0.45


def relative_luminance(color: Color) -> float:
    """WCAG 2.x relative luminance of an sRGB color, in [0, 1]."""

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = color.rgba[:3]
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def label_color(cell: Color, foreground: Color, background: Color) -> Color:
    """Text color for a label sitting on `cell` ([D113]): the darker of the
    theme pair on a bright cell, the lighter on a dark cell."""
    dark, light = sorted((foreground, background), key=relative_luminance)
    return dark if relative_luminance(cell) > _LABEL_LUMINANCE else light


def _label_ramp(name: str) -> Palette:
    """Continuous ramp for contrast computation: core palettes first, then
    matplotlib's registry when importable, else viridis. Only the *label
    color* rides on this — a fallback can cost contrast, never correctness."""
    from .palette import Palette, palettes  # noqa: PLC0415

    if name in palettes:
        return palettes.get(name)
    try:
        return Palette.from_matplotlib(name, n=32)
    except Exception:  # noqa: BLE001 — mpl absent or unknown name
        return palettes.get("viridis")


def _center_positions(centers) -> np.ndarray:
    arr = np.asarray(centers)
    if np.issubdtype(arr.dtype, np.number):
        return arr.astype("float64")
    return np.arange(len(arr), dtype="float64")


def heatmap_cell_labels(
    xs, ys, grid, *,
    spec: str = "auto", norm: str = "linear", vmin=None, vmax=None,
    gamma: float = 1.0, linthresh: float = 1.0, levels=None,
    colormap: str = "viridis",
    foreground: Color, background: Color, max_cells: int = CELL_LABEL_MAX,
) -> list[CellLabel]:
    """One `CellLabel` per finite cell of a heatmap grid ([D113]), computed
    once in core so every backend draws identical text: value formatted by the
    [D86] vocabulary (`"auto"` → `%g`), position at the cell center, color
    from `label_color` over the [D105]-normalized ramp color. Above
    `max_cells` it warns and returns nothing — honest, not silent."""
    from ._ticks import format_tick  # noqa: PLC0415

    g = np.asarray(grid, dtype="float64")
    if g.size > max_cells:
        import warnings  # noqa: PLC0415

        from ..errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(
            f"Heatmap annotate: {g.size} cells exceed the ~{max_cells} readability "
            "guard; labels skipped", QtvizWarning, stacklevel=2)
        return []
    normed, _lo, _hi = normalize_values(g, norm=norm, vmin=vmin, vmax=vmax,
                                        gamma=gamma, linthresh=linthresh, levels=levels)
    ramp = _label_ramp(colormap)
    fmt = "g" if spec == "auto" else spec
    xpos, ypos = _center_positions(xs), _center_positions(ys)
    out: list[CellLabel] = []
    for j in range(g.shape[0]):
        for i in range(g.shape[1]):
            v = g[j, i]
            if not np.isfinite(v):
                continue  # empty cell — nothing to say
            t = normed[j, i]
            cell = ramp.at(float(t)) if np.isfinite(t) else background
            out.append(CellLabel(i, j, float(xpos[i]), float(ypos[j]),
                                 format_tick(float(v), fmt),
                                 label_color(cell, foreground, background)))
    return out


def norm_engaged(element) -> bool:
    """Whether the [D105] norm surface is in use — legends/limits only then,
    so pre-existing plain rasters keep their exact look."""
    kind = getattr(element, "norm_kind", None)
    if kind is None:  # non-raster caller — the plain string field
        kind = getattr(element, "norm", "linear")
    return (kind != "linear"
            or getattr(element, "vmin", None) is not None
            or getattr(element, "vmax", None) is not None)
