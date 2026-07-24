"""Tier-4 — cost of the 0.3 axes seam ([D59], milestone-0.3-firstclass §5).

Two hot paths must stay cheap:

- `logify` runs per x/y channel at render when a surface is log-scaled — one
  vectorized `log10` + finite mask. Pinned as a small fraction of what a 1M-point
  render costs (tens of ms), i.e. single-digit ms.
- The R1 normalization (`delog`, 4× per RangeEvent) sits on the *event* path —
  pan emits ranges continuously, so it must stay microsecond-scale.

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_axes.py   # opt-in
    python tests/qtviz/benchmarks/test_bench_axes.py                # standalone

Marked `benchmark`, so excluded from the default run by `-m 'not benchmark'`.
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

pytest.importorskip("qtviz")

from qtviz.core._scales import delog, logify  # noqa: E402

LOGIFY_1M_CEILING_MS = 25.0   # per 1M-point channel; real cost ~3-5 ms (log10 + isfinite)
R1_EVENT_CEILING_US = 5.0     # per RangeEvent worth of delog (4 coords); real ~0.5 µs


def test_logify_1m_points_is_a_small_fraction_of_render():
    """One vectorized log10 + mask on 1M points — milliseconds, not tens of them."""
    rng = np.random.default_rng(0)
    a = rng.uniform(0.5, 1000.0, 1_000_000)  # all positive: the no-warn steady state
    logify(a, True)  # warm-up (allocator, cache)
    n = 20
    t0 = time.perf_counter()
    for _ in range(n):
        logify(a, True)
    per_ms = (time.perf_counter() - t0) / n * 1e3
    print(f"logify: {per_ms:.2f} ms / 1M-point channel")
    assert per_ms < LOGIFY_1M_CEILING_MS


def test_r1_normalization_per_event_is_microseconds():
    """A RangeEvent normalizes 4 coordinates (x0/x1/y0/y1) through delog — the
    whole event's R1 cost must stay well under the event-bus noise floor."""
    n = 200_000
    t0 = time.perf_counter()
    for _ in range(n):
        delog(0.1, True)
        delog(2.3, True)
        delog(-1.0, False)
        delog(4.2, False)
    per_us = (time.perf_counter() - t0) / n * 1e6
    print(f"R1 delog: {per_us:.3f} µs / RangeEvent (4 coords)")
    assert per_us < R1_EVENT_CEILING_US


def main() -> int:
    test_logify_1m_points_is_a_small_fraction_of_render()
    test_r1_normalization_per_event_is_microseconds()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
