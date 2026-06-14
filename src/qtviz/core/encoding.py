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
) -> tuple[np.ndarray, Legend]:
    """`values` → `(rgba, legend)` where rgba is `(N, 4)` float in [0, 1].

    `palette` colors categories; `continuous_palette` (default: `palette`) is the
    ramp for numeric columns. `kind="auto"` picks by dtype.
    """
    arr = np.asarray(values)
    categorical = is_categorical(arr) if kind == "auto" else kind == "categorical"
    if categorical:
        return _categorical(arr, palette, title)
    return _continuous(arr, continuous_palette or palette, vmin, vmax, title)


def _categorical(arr, palette: Palette, title) -> tuple[np.ndarray, Legend]:
    cats, codes = np.unique(arr, return_inverse=True)
    swatches = [palette[i % len(palette)] for i in range(len(cats))]
    lut = np.array([c.rgba for c in swatches], dtype="float64")
    rgba = lut[codes] if len(cats) else np.empty((0, 4))
    entries = tuple((str(c), swatches[i]) for i, c in enumerate(cats))
    return rgba, Legend(kind="categorical", title=title, entries=entries)


def _continuous(arr, palette: Palette, vmin, vmax, title) -> tuple[np.ndarray, Legend]:
    a = np.asarray(arr, dtype="float64")
    lo = float(np.nanmin(a)) if vmin is None else float(vmin)
    hi = float(np.nanmax(a)) if vmax is None else float(vmax)
    span = (hi - lo) or 1.0
    norm = np.nan_to_num(np.clip((a - lo) / span, 0.0, 1.0), nan=0.0)
    lut = np.array([palette.at(t / (_LUT_N - 1)).rgba for t in range(_LUT_N)], dtype="float64")
    rgba = lut[(norm * (_LUT_N - 1)).astype("int64")]
    ramp = tuple(palette.at(t) for t in _RAMP_STOPS)
    return rgba, Legend(kind="continuous", title=title, vmin=lo, vmax=hi, ramp=ramp)
