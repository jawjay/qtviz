"""Tier-4 — HoloViews adapter overhead (Phase 3, `milestone-holoviews-adapter.md`).

The adapter is a *thin* shim: it reads hv's public accessors and constructs qtviz
Elements — no rendering of its own. The thing worth guarding is that translation
stays cheap relative to the render it feeds, so `from_holoviews` never becomes the
bottleneck. We measure `from_holoviews` on a moderately large hv tree and assert a
soft ceiling; tighten against real numbers once the adapter lands.

Spec-first: `importorskip`s the adapter, so it skips until Phase 3 is implemented.
Marked `benchmark` → excluded from the default run (`-m 'not benchmark'`).

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_holoviews_adapter.py
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

qv = pytest.importorskip("qtviz")
# Adapter-absent skip BEFORE importing holoviews (numba/bokeh) — see the note in
# tests/qtviz/test_holoviews_adapter.py; collection must not import holoviews until
# the adapter lands.
_adapter = pytest.importorskip("qtviz.adapter.holoviews")
hv = pytest.importorskip("holoviews")
pd = pytest.importorskip("pandas")

from_holoviews = _adapter.from_holoviews

SIZES = (10_000, 100_000, 1_000_000)
SOFT_CEILING_1M_SECONDS = 1.0  # translation only; generous, revisit with real data


def _make_overlay(n: int):
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"a": rng.random(n), "b": rng.random(n)})
    return hv.Scatter(df, "a", "b") * hv.Curve(df, "a", "b")


def test_translation_is_cheap():
    timings = {}
    for n in SIZES:
        obj = _make_overlay(n)
        t0 = time.perf_counter()
        node = from_holoviews(obj)
        timings[n] = time.perf_counter() - t0
        assert isinstance(node, qv.Overlay)
    for n, dt in timings.items():
        print(f"from_holoviews overlay n={n:>9,}: {dt * 1e3:8.2f} ms")
    assert timings[1_000_000] < SOFT_CEILING_1M_SECONDS


if __name__ == "__main__":
    for n in SIZES:
        obj = _make_overlay(n)
        t0 = time.perf_counter()
        from_holoviews(obj)
        print(f"n={n:>9,}: {(time.perf_counter() - t0) * 1e3:8.2f} ms")
