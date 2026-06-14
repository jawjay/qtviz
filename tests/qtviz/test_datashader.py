"""Datashader rasterization — the big-data path (Phase 4a).

A scatter that would overplot/OOM is aggregated into a screen-resolution raster.
The routing (Scatter → Image) is backend-agnostic and runs off the GUI thread;
a dask source stays lazy so aggregation is out-of-core.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("datashader")

from qtviz.data import as_data_ref, pipeline  # noqa: E402
from qtviz.ext.datashader import channel_frame, rasterize_points, rasterize_scatter  # noqa: E402

pytestmark = pytest.mark.tier1


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    n = 50_000
    return {"x": rng.normal(size=n), "y": rng.normal(size=n)}


@pytest.fixture
def reset_threshold():
    saved = pipeline._RASTER_THRESHOLD
    yield
    pipeline._RASTER_THRESHOLD = saved


# ── the rasterizer ───────────────────────────────────────────────────────────
def test_rasterize_returns_rgba_and_bounds(data):
    rgba, bounds = rasterize_scatter(qv.Scatter(data, x="x", y="y"), width=120, height=80)
    assert rgba.shape == (80, 120, 4) and rgba.dtype == np.uint8
    assert rgba[..., 3].max() > 0  # some pixels were painted
    xmin, ymin, xmax, ymax = bounds
    assert xmin < xmax and ymin < ymax


def test_rasterize_density_concentrates(data):
    # all points in a tight cluster → only a few pixels carry the density
    cluster = {"x": np.full(10_000, 1.0), "y": np.full(10_000, 2.0)}
    rgba, _ = rasterize_points(_pandas(cluster), "x", "y", width=50, height=50)
    painted = int((rgba[..., 3] > 0).sum())
    assert 0 < painted <= 25  # concentrated, not spread across the canvas


def test_channel_frame_keeps_dask_lazy(data):
    dd = pytest.importorskip("dask.dataframe")
    pd = pytest.importorskip("pandas")
    ddf = dd.from_pandas(pd.DataFrame(data), npartitions=4)
    frame = channel_frame(as_data_ref(ddf), {"x": "x", "y": "y"})
    assert type(frame).__module__.startswith(("dask", "dask_expr"))  # never materialized


def test_channel_frame_resolves_accessors(data):
    frame = channel_frame(as_data_ref(data), {"x": "x", "y": qv.col("x") + qv.col("y")})
    np.testing.assert_allclose(np.asarray(frame["x"]), data["x"])
    np.testing.assert_allclose(np.asarray(frame["y"]), data["x"] + data["y"])


# ── pipeline routing ─────────────────────────────────────────────────────────
def test_scale_native_is_not_rasterized(data):
    assert not pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", scale="native"))


def test_scale_datashader_always_rasterizes(data):
    assert pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", scale="datashader"))


def test_scale_auto_routes_above_threshold(data, reset_threshold):
    pipeline.set_raster_threshold(10_000)  # data is 50k
    assert pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", scale="auto"))
    pipeline.set_raster_threshold(10_000_000)
    assert not pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", scale="auto"))


def test_scale_auto_routes_unknown_size_lazy(data):
    dd = pytest.importorskip("dask.dataframe")
    pd = pytest.importorskip("pandas")
    ddf = dd.from_pandas(pd.DataFrame(data), npartitions=2)  # size() is None
    assert pipeline._needs_rasterize(qv.Scatter(ddf, x="x", y="y", scale="auto"))


def test_resolve_transforms_scatter_to_image(data):
    scatter = qv.Scatter(data, x="x", y="y", scale="datashader")
    image = pipeline.resolve_node(scatter)
    assert isinstance(image, qv.Image)
    assert image.id == scatter.id  # source id carried (for events)


def test_rasterized_node_is_lazy(data):
    assert pipeline.node_is_lazy(qv.Scatter(data, x="x", y="y", scale="datashader"))  # → off-thread


def _pandas(d):
    import pandas as pd

    return pd.DataFrame(d)


# ── async render through the View (Tier 2) ───────────────────────────────────
@pytest.mark.tier2
def test_datashaded_scatter_renders_async(data, qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", scale="datashader"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle is None and view.loading  # aggregated off-thread
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    assert view.handle is not None
