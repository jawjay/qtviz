"""Tier-4 — cost of the 0.4 stats core (milestone-0.4 §8).

`grid_reduce` runs per Heatmap render; `box_stats`/`kde` per BoxPlot/Violin
render. All are vectorized numpy — pinned at ms-scale so a render never stalls
on its statistics.

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_stats.py   # opt-in
    python tests/qtviz/benchmarks/test_bench_stats.py                # standalone
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

pytest.importorskip("qtviz")

from qtviz.core._stats import box_stats, grid_reduce, kde  # noqa: E402

GRID_1M_CEILING_MS = 120.0   # 1M rows → 100×100 grid (unique + 2 bincounts)
BOX_100K_CEILING_MS = 20.0   # percentiles + masks
KDE_100K_CEILING_MS = 120.0  # 100k × 128 Gaussian evaluations


def _timed(fn, n=5):
    fn()  # warm-up
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1e3


def test_grid_reduce_1m_rows():
    rng = np.random.default_rng(0)
    x = rng.integers(0, 100, 1_000_000).astype("float64")
    y = rng.integers(0, 100, 1_000_000).astype("float64")
    z = rng.normal(size=1_000_000)
    ms = _timed(lambda: grid_reduce(x, y, z, "mean"))
    print(f"grid_reduce: {ms:.1f} ms / 1M rows → 100×100 mean grid")
    assert ms < GRID_1M_CEILING_MS


def test_box_stats_100k():
    rng = np.random.default_rng(1)
    v = rng.normal(size=100_000)
    ms = _timed(lambda: box_stats(v))
    print(f"box_stats: {ms:.1f} ms / 100k values")
    assert ms < BOX_100K_CEILING_MS


def test_kde_100k():
    rng = np.random.default_rng(2)
    v = rng.normal(size=100_000)
    ms = _timed(lambda: kde(v), n=3)
    print(f"kde: {ms:.1f} ms / 100k values × 128-pt grid")
    assert ms < KDE_100K_CEILING_MS


def main() -> int:
    test_grid_reduce_1m_rows()
    test_box_stats_100k()
    test_kde_100k()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
