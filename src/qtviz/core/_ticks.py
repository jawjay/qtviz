"""Tick formatting ([D86]) — one portable vocabulary, rendered per backend.

`AxisSpec.tick_format` accepts `"auto"` (the backend's default), a Python
format-spec string (`".2f"`, `",d"`, `".0%"`, `".2e"`, …), or `"eng"` (SI
prefixes). matplotlib and pyqtgraph format through `format_tick` below;
webengine translates to Plotly's d3-format, whose spec mini-language matches
Python's for these forms. Validation happens at `AxisSpec` construction —
a bad spec fails loud, not at render.
"""

from __future__ import annotations

import math

from ..errors import ValidationError

# Integer presentation types: ticks arrive as floats, so these format round(v).
_INT_TYPES = set("bcdoxXn")

# SI prefixes for 10**-24 … 10**24 (index offset +8 in steps of 10**3).
_SI = ("y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E", "Z", "Y")


def validate_tick_format(spec: str, *, who: str = "AxisSpec") -> None:
    if spec in ("auto", "eng"):
        return
    try:
        format_tick(1234.5678, spec)
    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"{who}: tick_format must be 'auto', 'eng', or a Python format spec "
            f"(e.g. '.2f', ',d', '.0%'); got {spec!r} ({e})"
        ) from e


def format_tick(value: float, spec: str) -> str:
    """One tick label under `spec` (never `"auto"` — the caller keeps the
    backend default for that)."""
    if spec == "eng":
        return _eng(value)
    if spec and spec[-1] in _INT_TYPES:
        return format(int(round(value)), spec)
    return format(value, spec)


def _eng(v: float) -> str:
    if v == 0 or not math.isfinite(v):
        return f"{v:g}"
    exp3 = min(8, max(-8, math.floor(math.log10(abs(v)) / 3.0)))
    return f"{v / 10 ** (3 * exp3):g}{_SI[exp3 + 8]}"


def plotly_tick_format(spec: str) -> str:
    """The d3-format equivalent Plotly needs: `eng` → `~s` (SI suffix); Python
    format specs pass through (the d3 mini-language is modeled on Python's)."""
    return "~s" if spec == "eng" else spec
