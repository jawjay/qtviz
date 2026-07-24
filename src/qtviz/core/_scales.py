"""Log-scale coordinate helpers (0.3 increment 2; [D59], feasibility §10).

Pure numpy, no Qt. Two directions across the seam:

- `logify` — data space → exponent space, applied by renderers that must
  pre-transform (pyqtgraph's bare items don't implement `setLogMode`). Non-positive
  values are *masked to NaN* rather than removed, so array length — and with it
  pick/hover row alignment and per-point style arrays — is preserved; visually a
  NaN point is dropped, matching matplotlib's masking.
- `delog` — exponent space → data space, applied once at every emit/state boundary
  (the R1 normalization, feasibility §10.3).
"""

from __future__ import annotations

import warnings

import numpy as np

from ..errors import QtvizWarning


def logify(arr: np.ndarray, is_log: bool) -> np.ndarray:
    """`log10(arr)` when `is_log`, else `arr` untouched. Non-positive values warn
    once (per call) and become NaN ([D59] drop-and-warn)."""
    if not is_log:
        return arr
    a = np.asarray(arr, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.log10(a)
    dropped = ~np.isfinite(out) & np.isfinite(a)  # produced by values <= 0
    if dropped.any():
        warnings.warn(
            f"{int(dropped.sum())} non-positive value(s) dropped under log scale",
            QtvizWarning,
            stacklevel=2,
        )
    out[~np.isfinite(out)] = np.nan
    return out


def delog(v: float, is_log: bool) -> float:
    """One coordinate back to data space: `10**v` when `is_log`, else `v`."""
    return float(10.0**v) if is_log else float(v)


def log_lim(lim: tuple[float, float], *, axis: str, backend: str) -> tuple[float, float] | None:
    """A data-space `AxisSpec.lim` in exponent space, or `None` (with a warning)
    when the limits aren't usable under log (non-positive endpoint)."""
    lo, hi = lim
    if lo <= 0 or hi <= 0:
        warnings.warn(
            f"{backend}: {axis} lim={lim!r} has a non-positive endpoint and can't "
            f"apply under log scale; ignoring the declarative limits.",
            QtvizWarning,
            stacklevel=2,
        )
        return None
    return (float(np.log10(lo)), float(np.log10(hi)))
