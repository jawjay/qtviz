"""Tier-4 — cost of the 0.2 hardening seam ([D51]/[D53], milestone-0.2-hardening §4).

The §3.4 honor-or-warn check runs on *every* element at *every* render, and the
`native()` id→primitive map is built per render — so both must be free. The common
(all-honored) path is a handful of set-membership checks; `native()` is a dict get.
This pins that: per-element check cost and per-lookup cost stay microsecond-scale,
and the map is complete after a large render.

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_degrade.py   # opt-in
    python tests/qtviz/benchmarks/test_bench_degrade.py                # standalone

Marked `benchmark`, so excluded from the default run by `-m 'not benchmark'`.
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

qv = pytest.importorskip("qtviz")

from qtviz.core import _degrade  # noqa: E402

CHECK_CEILING_US = 20.0   # per element; real cost ~1 µs (set lookups, cached defaults)
NATIVE_CEILING_US = 5.0   # per native() lookup; a dict.get
RENDER_CEILING_S = 5.0    # 200-element overlay build+render; generous


def _scatter():
    # several non-default options set, all honored on a typical backend → exercises
    # the steady-state path (the `opt in honored` short-circuit, no warn).
    return qv.Scatter(
        {"x": [0.0, 1.0], "y": [0.0, 1.0]}, x="x", y="y",
        marker="square", alpha=0.5, size=8, color="#5fa8ff",
    )


def test_check_recommended_per_element_is_cheap():
    """The check adds microseconds per element — never a fraction of render time."""
    el = _scatter()
    honored = frozenset(el.RECOMMENDED_OPTIONS)  # common case: backend honors them
    _degrade.reset()
    n = 20_000
    t0 = time.perf_counter()
    for _ in range(n):
        _degrade.check_recommended(el, backend_name="b", honored=honored)
    per_us = (time.perf_counter() - t0) / n * 1e6
    print(f"check_recommended: {per_us:.3f} µs/element (all-honored path)")
    assert per_us < CHECK_CEILING_US


def test_native_map_build_and_lookup(qapp):
    """A 200-element overlay's id→primitive map is complete and O(1) to query."""
    import qtviz.backends as B

    try:
        backend = B.get("pyqtgraph")
    except Exception:
        pytest.skip("pyqtgraph unavailable")

    n = 200
    data = {"x": [0.0, 1.0], "y": [0.0, 1.0]}
    elements = [qv.Scatter(data, x="x", y="y") for _ in range(n)]
    overlay = qv.Overlay(elements)

    t0 = time.perf_counter()
    handle = backend.render(overlay, theme=qv.Theme.light())
    render_s = time.perf_counter() - t0
    assert len(handle._natives) == n  # every element reachable via native()

    ids = [el.id for el in elements]
    t1 = time.perf_counter()
    for i in range(10_000):
        handle.native(ids[i % n])
    lookup_us = (time.perf_counter() - t1) / 10_000 * 1e6
    handle.dispose()

    print(f"render {n}-element overlay: {render_s * 1e3:.1f} ms | "
          f"native() lookup: {lookup_us:.3f} µs")
    assert render_s < RENDER_CEILING_S
    assert lookup_us < NATIVE_CEILING_US


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        print("PySide6 not available")
        return 1
    app = QApplication.instance() or QApplication([])
    test_check_recommended_per_element_is_cheap()
    test_native_map_build_and_lookup(app)
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
