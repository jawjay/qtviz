"""Tier-4 — render performance harness (roadmap D1, dev-plan §5.4).

Targets: a 1M-row Scatter renders and stays interactive (≥30 FPS pan/zoom,
brush < 16 ms). True interactive FPS needs a visible window and is a manual
gate; here we measure what *is* reproducible headless — time to build + render
+ force one paint — across sizes, and assert a soft ceiling at 1M.

Two ways to run:
    pytest -m benchmark tests/qtviz/benchmarks/test_bench_render.py   # opt-in
    python tests/qtviz/benchmarks/test_bench_render.py                # standalone

Marked `benchmark`, so excluded from the default run by `-m 'not benchmark'`.
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

SIZES = (10_000, 100_000, 1_000_000)
SOFT_CEILING_1M_SECONDS = 5.0  # generous; tighten against real D1 numbers later


def make_points(n: int) -> dict:
    import numpy as np

    rng = np.random.default_rng(0)
    return {"x": rng.random(n), "y": rng.random(n)}


def resolve_backend(name: str | None = None):
    """First registered backend (or a named one), or None if qtviz/backends
    aren't available yet."""
    try:
        import qtviz.backends as B

        names = [getattr(b, "name", b) for b in B.list_available()]
        if not names:
            return None
        pick = name or names[0]
        registry = {getattr(b, "name", b): b for b in B.list_available()}
        for resolve in (lambda: B.get(pick), lambda: registry[pick]):
            try:
                return resolve()
            except Exception:
                continue
    except Exception:
        return None
    return None


def time_render(backend, n: int) -> float:
    """Seconds to build a Scatter of n points, render it, and force one paint."""
    import contextlib

    import qtviz as qv

    points = make_points(n)
    t0 = time.perf_counter()
    handle = backend.render(qv.Scatter(points, x="x", y="y"), theme=qv.Theme.light())
    with contextlib.suppress(Exception):
        handle.widget.grab()  # force a real paint pass
    elapsed = time.perf_counter() - t0
    handle.dispose()
    return elapsed


# ── pytest entry point (opt-in via -m benchmark) ─────────────────────────────
def test_render_scaling(qapp):
    backend = resolve_backend()
    if backend is None:
        pytest.skip("no backend registered yet")
    timings = {n: time_render(backend, n) for n in SIZES}
    for n, secs in timings.items():
        print(f"  {backend.name:12s} {n:>9,} pts  {secs * 1e3:8.1f} ms")
    assert timings[1_000_000] < SOFT_CEILING_1M_SECONDS


# ── standalone ───────────────────────────────────────────────────────────────
def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        print("PySide6 not available")
        return 1
    app = QApplication.instance() or QApplication([])
    backend = resolve_backend()
    if backend is None:
        print("No qtviz backend registered yet — nothing to benchmark.")
        return 0
    print(f"render scaling — backend={backend.name}")
    for n in SIZES:
        print(f"  {n:>9,} pts  {time_render(backend, n) * 1e3:8.1f} ms")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
