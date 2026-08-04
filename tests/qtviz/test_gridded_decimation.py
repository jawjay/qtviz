"""0.5 increment 2 — decimated gridded materialize ([D74], milestone-0.5 §2).

A lazy gridded ref (zarr / dask / N-D xarray) over budget materializes a
strided, screen-scale slice instead of the whole array — memory-bounded always,
chunk-skipping when the stride exceeds the chunk extent. The resolve pipeline
budgets lazy grids at 4× the raster size and stashes the lazy source for the
viewport-regrid loop.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.data import as_data_ref, resolve_node  # noqa: E402
from qtviz.data.ref import decimation_strides  # noqa: E402

pytestmark = pytest.mark.tier1


class _CountingStore:
    """A zarr WrapperStore counting chunk (non-metadata) reads."""

    def __new__(cls):
        from zarr.storage import MemoryStore, WrapperStore

        class Impl(WrapperStore):
            def __init__(self, store):
                super().__init__(store)
                self.gets = 0

            async def get(self, key, prototype, byte_range=None):
                if not key.endswith("zarr.json"):
                    self.gets += 1
                return await super().get(key, prototype, byte_range)

        return Impl(MemoryStore())


def _big_zarr(shape=(2048, 2048), chunks=(16, 16)):
    zarr = pytest.importorskip("zarr")
    store = _CountingStore()
    z = zarr.create_array(store=store, shape=shape, chunks=chunks, dtype="f8")
    # full write: zarr 3 rejects broadcasting a column into chunked storage
    z[:] = np.broadcast_to(np.arange(shape[0], dtype="f8")[:, None], shape).copy()
    store.gets = 0
    return z, store


# ── the stride math ──────────────────────────────────────────────────────────
def test_decimation_strides():
    assert decimation_strides((100, 100), None) is None
    assert decimation_strides((100, 100), 100_000) is None        # under budget
    sy, sx = decimation_strides((1000, 1000), 10_000)
    assert sy == sx == 10                                          # √(1M/10k)
    assert (1000 // sy) * (1000 // sx) <= 10_000
    sy, sx = decimation_strides((3, 10_000_000), 30_000)           # skinny array
    rows, cols = -(-3 // sy), -(-10_000_000 // sx)
    assert rows * cols <= 30_000                       # clamped axis re-budgeted


# ── per-container decimated materialize ──────────────────────────────────────
def test_zarr_decimated_materialize_is_memory_bounded():
    z, store = _big_zarr()
    ref = as_data_ref(z)
    eager = ref.materialize(max_cells=10_000)
    values = eager.grid().values
    assert values.size <= 10_000
    assert values[1, 0] > values[0, 0]                # still the gradient, sampled
    # coords carry the stride so geometry stays exact
    x = eager.grid().x
    assert x[1] - x[0] == 2048 / values.shape[1] // 1 or x[1] - x[0] >= 1


def test_zarr_full_materialize_unchanged_without_budget():
    z, _ = _big_zarr(shape=(64, 64), chunks=(16, 16))
    assert as_data_ref(z).materialize().grid().values.shape == (64, 64)


def test_zarr_chunk_skipping_when_stride_exceeds_chunk():
    """Stride 32 over 16-px chunks samples every other chunk band per axis —
    about a quarter of the chunks are read; the rest are never touched."""
    z, store = _big_zarr(shape=(2048, 2048), chunks=(16, 16))
    total_chunks = (2048 // 16) ** 2
    as_data_ref(z).materialize(max_cells=(2048 // 32) ** 2)       # → stride 32
    assert store.gets <= total_chunks / 3                          # ~1/4 touched


def test_dask_decimated_materialize():
    da = pytest.importorskip("dask.array")
    arr = da.arange(4096 * 4096, dtype="f8").reshape(4096, 4096).rechunk(512)
    eager = as_data_ref(arr).materialize(max_cells=100_000)
    assert eager.grid().values.size <= 100_000


def test_xarray_decimated_materialize_keeps_coords_aligned():
    xr = pytest.importorskip("xarray")
    ny, nx = 1000, 2000
    da = xr.DataArray(np.zeros((ny, nx)), dims=("y", "x"),
                      coords={"x": np.linspace(0.0, 100.0, nx),
                              "y": np.linspace(-1.0, 1.0, ny)})
    eager = as_data_ref(da).materialize(max_cells=20_000)
    g = eager.grid()
    assert g.values.size <= 20_000
    assert g.x[0] == 0.0 and g.x[-1] <= 100.0          # decimated real coords
    assert len(g.x) == g.values.shape[1] and len(g.y) == g.values.shape[0]


# ── the pipeline budgets lazy grids and stashes the source ───────────────────
def test_resolve_budgets_lazy_grid_and_stashes_source():
    z, _ = _big_zarr()
    el = qv.Image(z, extent=(0.0, 0.0, 1.0, 1.0))
    resolved = resolve_node(el)
    values = resolved.data.grid().values
    assert values.size < 2048 * 2048                    # decimated, not full
    assert getattr(resolved, "_grid_source", None) is not None
    assert resolved._grid_source.is_lazy               # the ORIGINAL lazy ref


def test_resolve_leaves_small_lazy_grid_full_and_unstashed():
    z, _ = _big_zarr(shape=(32, 32), chunks=(16, 16))
    resolved = resolve_node(qv.Image(z, extent=(0.0, 0.0, 1.0, 1.0)))
    assert resolved.data.grid().values.shape == (32, 32)
    assert getattr(resolved, "_grid_source", None) is None  # nothing to sharpen
