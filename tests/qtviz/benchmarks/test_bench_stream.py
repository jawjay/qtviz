"""Tier-4 — cost of the 0.6 live path (milestone-0.6-live §6).

`append` runs on the producer's thread (µs-scale or it back-pressures the
source); `set_element_data` is the per-frame refresh write (ms-scale at a 100k
window — the interactive-rate claim).

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_stream.py   # opt-in
    python tests/qtviz/benchmarks/test_bench_stream.py                # standalone
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

qv = pytest.importorskip("qtviz")

APPEND_CEILING_US = 200.0     # per 25-row batch append into a 100k window
REFRESH_CEILING_MS = 25.0     # resolve + setData of a 100k-point window


def test_append_cost():
    feed = qv.stream({"t": float, "v": float}, window=100_000)
    feed.append(t=np.arange(100_000.0), v=np.arange(100_000.0))  # warm, full window
    batch_t, batch_v = np.arange(25.0), np.arange(25.0)
    n = 2_000
    t0 = time.perf_counter()
    for _ in range(n):
        feed.append(t=batch_t, v=batch_v)
    per_us = (time.perf_counter() - t0) / n * 1e6
    print(f"append (25-row batch into a rolling 100k window): {per_us:.1f} µs")
    assert per_us < APPEND_CEILING_US


def test_refresh_cost_at_100k(qapp):
    import qtviz.backends as B

    try:
        backend = B.get("pyqtgraph")
    except Exception:
        pytest.skip("pyqtgraph unavailable")
    feed = qv.stream({"t": float, "v": float}, window=100_000)
    feed.append(t=np.arange(100_000.0), v=np.arange(100_000.0))
    el = qv.Curve(feed, x="t", y="v")
    handle = backend.render(el, theme=qv.Theme.dark())
    n = 20
    t0 = time.perf_counter()
    for _ in range(n):
        arrays = feed.resolve_channels(el.channels())
        assert handle.set_element_data(el.id, arrays)
    per_ms = (time.perf_counter() - t0) / n * 1e3
    handle.dispose()
    print(f"refresh (resolve + setData @ 100k window): {per_ms:.1f} ms")
    assert per_ms < REFRESH_CEILING_MS


def test_lowered_refresh_cost_at_100k(qapp):
    """[D128]: the lowered fast path re-*lowers* per frame (Ecdf: an
    O(n log n) sort) before the setData write — budget both under the same
    interactive-rate ceiling as the native path."""
    import qtviz.backends as B

    try:
        backend = B.get("pyqtgraph")
    except Exception:
        pytest.skip("pyqtgraph unavailable")
    feed = qv.stream({"v": float}, window=100_000)
    feed.append(v=np.random.default_rng(0).normal(size=100_000))
    el = qv.Ecdf(feed, value="v")
    handle = backend.render(el, theme=qv.Theme.dark())
    n = 20
    t0 = time.perf_counter()
    for _ in range(n):
        arrays = feed.resolve_channels(el.channels())
        assert handle.set_element_data(el.id, arrays)
    per_ms = (time.perf_counter() - t0) / n * 1e3
    handle.dispose()
    print(f"lowered refresh (resolve + relower + setData, Ecdf @ 100k): {per_ms:.1f} ms")
    assert per_ms < REFRESH_CEILING_MS


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    test_append_cost()
    test_refresh_cost_at_100k(app)
    test_lowered_refresh_cost_at_100k(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
