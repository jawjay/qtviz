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
