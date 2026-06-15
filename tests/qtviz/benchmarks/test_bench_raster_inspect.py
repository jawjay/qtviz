"""Tier-4 — raster reverse-lookup per-hover cost ([D46], milestone-raster-inspect.md).

`RasterAggregate.value_at` runs on every (throttled) mouse-move over a datashaded
view, so it must stay O(1) and microsecond-scale — never creeping into the event
path. Pure numpy index math; no datashader needed.

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_raster_inspect.py
"""

from __future__ import annotations

import time

import numpy as np
import pytest

pytestmark = pytest.mark.benchmark

qv = pytest.importorskip("qtviz")  # noqa: F841
from qtviz.ext.datashader import RasterAggregate  # noqa: E402

SOFT_CEILING_US = 50.0  # per lookup; generous, real cost is ~1 µs


def test_value_at_is_cheap():
    rng = np.random.default_rng(0)
    agg = RasterAggregate(rng.random((600, 800)), (0.0, 0.0, 10.0, 10.0), "mean")
    qs = rng.uniform(0.0, 10.0, (10_000, 2))
    t0 = time.perf_counter()
    for x, y in qs:
        agg.value_at(x, y)
    per_call_us = (time.perf_counter() - t0) / len(qs) * 1e6
    print(f"value_at: {per_call_us:.3f} µs/call")
    assert per_call_us < SOFT_CEILING_US
