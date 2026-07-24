"""Tier-4 — cost of the 0.5 array core (milestone-0.5 §6).

Decimated materialize is the render-path read for big lazy grids; regrid sits
on the zoom path. Both pinned so a huge array never costs array-scale time.

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_regrid.py   # opt-in
    python tests/qtviz/benchmarks/test_bench_regrid.py                # standalone
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

pytest.importorskip("qtviz")
zarr = pytest.importorskip("zarr")

from qtviz.core.palette import palettes  # noqa: E402
from qtviz.data import as_data_ref  # noqa: E402
from qtviz.data.regrid import make_regrid  # noqa: E402

# NB: on a MemoryStore the full read is a memcpy — decimation's win there is
# *memory* (≤ budget cells vs 512 MB) plus strictly-partial I/O on windowed
# reads (pinned in tier-1); these ceilings pin absolute cost, not a speedup.
DECIMATED_CEILING_MS = 400.0   # 8k×8k → ≤1.92M cells
REGRID_CEILING_MS = 150.0      # zoom-path: window read + shade at widget res


def _array(shape=(8192, 8192), chunks=(512, 512)):
    z = zarr.create_array(store=None, shape=shape, chunks=chunks, dtype="f8")
    z[:] = np.broadcast_to(np.arange(shape[0], dtype="f8")[:, None], shape).copy()
    return z


def test_decimated_vs_full_materialize():
    ref = as_data_ref(_array())
    t0 = time.perf_counter()
    ref.materialize(max_cells=4 * 800 * 600)
    dec_ms = (time.perf_counter() - t0) * 1e3
    eager = ref.materialize(max_cells=4 * 800 * 600)
    t0 = time.perf_counter()
    ref.materialize()
    full_ms = (time.perf_counter() - t0) * 1e3
    print(f"materialize 8k×8k zarr: decimated {dec_ms:.0f} ms vs full {full_ms:.0f} ms")
    assert dec_ms < DECIMATED_CEILING_MS
    assert eager.grid().values.size <= 4 * 800 * 600   # the memory guarantee


def test_regrid_zoom_path_cost():
    ref = as_data_ref(_array())
    rasterize = make_regrid((0.0, 0.0, 10.0, 10.0), palettes.get("viridis"))
    rasterize(ref, width=800, height=600, x_range=(0.0, 1.0), y_range=(0.0, 1.0))  # warm
    t0 = time.perf_counter()
    n = 5
    for _ in range(n):
        rasterize(ref, width=800, height=600, x_range=(0.0, 1.0), y_range=(0.0, 1.0))
    per_ms = (time.perf_counter() - t0) / n * 1e3
    print(f"regrid (window read + shade @ 800×600): {per_ms:.0f} ms")
    assert per_ms < REGRID_CEILING_MS


def main() -> int:
    test_decimated_vs_full_materialize()
    test_regrid_zoom_path_cost()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
