"""Calendar-time helpers ([D94]) — the canonical time data-space is **epoch
seconds, UTC** on every backend.

datetime64 columns pass through the data layer untouched and become epoch
seconds at each backend's column seam (`_col`/`_floats`), so events, state,
brushes and `ViewState` stay plain floats in one space (R1) and round-trip
across backend switches. Calendar rendering is per-backend axis dressing:
matplotlib gets an adaptive strftime formatter, pyqtgraph a `DateAxisItem`
(UTC), webengine a Plotly date axis (milliseconds at its boundary).
Timezone policy: datetime64 is tz-naive by construction and is treated as UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np


def is_datetime(arr) -> bool:
    dtype = getattr(arr, "dtype", None)
    return dtype is not None and dtype.kind == "M"


def to_epoch_seconds(arr) -> np.ndarray:
    """datetime64[*] → float64 epoch seconds (ns-precise)."""
    return np.asarray(arr).astype("datetime64[ns]").astype("int64") / 1e9


def as_float_seconds(arr) -> np.ndarray:
    """The universal column seam: datetime64 → epoch seconds, everything else →
    float64 (what `np.asarray(..., float64)` did — minus the silent
    nanosecond-magnitude coercion datetime used to get)."""
    a = np.asarray(arr)
    if a.dtype.kind == "M":
        return to_epoch_seconds(a)
    return np.asarray(a, dtype="float64")


# Visible-span thresholds → strftime spec for "auto" calendar ticks.
_SPANS: tuple[tuple[float, str], ...] = (
    (2 * 365 * 86400.0, "%Y"),
    (60 * 86400.0, "%Y-%m"),
    (2 * 86400.0, "%m-%d"),
    (2 * 3600.0, "%H:%M"),
)


def auto_time_spec(span_seconds: float) -> str:
    for lo, spec in _SPANS:
        if span_seconds >= lo:
            return spec
    return "%H:%M:%S"


def format_time(seconds: float, spec: str) -> str:
    """One tick label: epoch seconds through `strftime` (UTC)."""
    return datetime.fromtimestamp(float(seconds), tz=UTC).strftime(spec)


def format_time_auto(seconds: float, span_seconds: float) -> str:
    return format_time(seconds, auto_time_spec(abs(float(span_seconds)) or 1.0))


_YEAR_S = 365.2425 * 86400.0
# (unit, multiple, approx seconds, strftime spec) — first fit wins.
_TICK_LADDER: tuple[tuple[str, int, float, str], ...] = (
    ("s", 1, 1.0, "%H:%M:%S"), ("s", 2, 2.0, "%H:%M:%S"),
    ("s", 5, 5.0, "%H:%M:%S"), ("s", 10, 10.0, "%H:%M:%S"),
    ("s", 15, 15.0, "%H:%M:%S"), ("s", 30, 30.0, "%H:%M:%S"),
    ("m", 1, 60.0, "%H:%M"), ("m", 2, 120.0, "%H:%M"),
    ("m", 5, 300.0, "%H:%M"), ("m", 10, 600.0, "%H:%M"),
    ("m", 15, 900.0, "%H:%M"), ("m", 30, 1800.0, "%H:%M"),
    ("h", 1, 3600.0, "%H:%M"), ("h", 2, 7200.0, "%H:%M"),
    ("h", 3, 10800.0, "%H:%M"), ("h", 6, 21600.0, "%H:%M"),
    ("h", 12, 43200.0, "%H:%M"),
    ("D", 1, 86400.0, "%m-%d"), ("D", 2, 172800.0, "%m-%d"),
    ("D", 7, 604800.0, "%m-%d"), ("D", 14, 1209600.0, "%m-%d"),
    ("M", 1, _YEAR_S / 12, "%Y-%m"), ("M", 2, _YEAR_S / 6, "%Y-%m"),
    ("M", 3, _YEAR_S / 4, "%Y-%m"), ("M", 6, _YEAR_S / 2, "%Y-%m"),
)


def _calendar_range(lo: float, hi: float, unit: str, mult: int) -> np.ndarray:
    """Unit-boundary tick positions in [lo, hi] (epoch seconds, UTC). Years
    and months align through datetime64 calendar arithmetic; days and below
    are fixed-width, so plain arithmetic alignment IS the boundary."""
    if unit in ("Y", "M"):
        start = np.datetime64(int(lo * 1000), "ms").astype(f"datetime64[{unit}]")
        end = np.datetime64(int(hi * 1000), "ms").astype(f"datetime64[{unit}]") + 1
        marks = np.arange(start, end + 1, mult)
        if unit == "Y":  # align multiples to the decade/century grid
            years = marks.astype("int64") + 1970
            marks = marks[(years % mult) == 0]
        secs = marks.astype("datetime64[s]").astype("int64").astype("float64")
    else:
        step = {"s": 1.0, "m": 60.0, "h": 3600.0, "D": 86400.0}[unit] * mult
        start = np.ceil(lo / step) * step
        secs = np.arange(start, hi + step / 2, step)
    return secs[(secs >= lo) & (secs <= hi)]


def time_ticks(lo: float, hi: float, target: int = 6) -> tuple[np.ndarray, str]:
    """Calendar-aligned tick positions + strftime spec for a [lo, hi]
    epoch-seconds window ([D104]) — one implementation, consumed by the
    matplotlib locator (pg's `DateAxisItem` is already calendar-native)."""
    if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
        return np.array([]), "%Y-%m-%d"
    span = hi - lo
    for unit, mult, approx, spec in _TICK_LADDER:
        if span / approx <= target:
            return _calendar_range(lo, hi, unit, mult), spec
    # years: 1/2/5 ladder scaled by powers of ten
    per_year = span / _YEAR_S
    mult = 1
    for candidate in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
        mult = candidate
        if per_year / candidate <= target:
            break
    return _calendar_range(lo, hi, "Y", mult), "%Y"
