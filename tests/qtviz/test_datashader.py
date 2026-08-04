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
from qtviz.ext.datashader import (  # noqa: E402
    channel_frame,
    rasterize_curve,
    rasterize_element,
    rasterize_points,
    rasterize_scatter,
)

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
    r = rasterize_scatter(qv.Scatter(data, x="x", y="y"), width=120, height=80)
    rgba, bounds = r.rgba, r.bounds
    assert rgba.shape == (80, 120, 4) and rgba.dtype == np.uint8
    assert rgba[..., 3].max() > 0  # some pixels were painted
    xmin, ymin, xmax, ymax = bounds
    assert xmin < xmax and ymin < ymax


def test_rasterize_density_concentrates(data):
    # all points in a tight cluster → only a few pixels carry the density
    cluster = {"x": np.full(10_000, 1.0), "y": np.full(10_000, 2.0)}
    rgba = rasterize_points(_pandas(cluster), "x", "y", width=50, height=50).rgba
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
    assert not pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", raster="native"))


def test_scale_datashader_always_rasterizes(data):
    assert pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", raster="datashader"))


def test_scale_auto_routes_above_threshold(data, reset_threshold):
    pipeline.set_raster_threshold(10_000)  # data is 50k
    assert pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", raster="auto"))
    pipeline.set_raster_threshold(10_000_000)
    assert not pipeline._needs_rasterize(qv.Scatter(data, x="x", y="y", raster="auto"))


def test_scale_auto_routes_unknown_size_lazy(data):
    dd = pytest.importorskip("dask.dataframe")
    pd = pytest.importorskip("pandas")
    ddf = dd.from_pandas(pd.DataFrame(data), npartitions=2)  # size() is None
    assert pipeline._needs_rasterize(qv.Scatter(ddf, x="x", y="y", raster="auto"))


def test_resolve_transforms_scatter_to_image(data):
    scatter = qv.Scatter(data, x="x", y="y", raster="datashader")
    image = pipeline.resolve_node(scatter)
    assert isinstance(image, qv.Image)
    assert image.id == scatter.id  # source id carried (for events)


def test_rasterized_node_is_lazy(data):
    el = qv.Scatter(data, x="x", y="y", raster="datashader")
    assert pipeline.node_is_lazy(el)  # → off-thread


def _pandas(d):
    import pandas as pd

    return pd.DataFrame(d)


# ── expanded coverage: lines, categorical, value aggregation (D22) ───────────
@pytest.fixture
def typed_data():
    rng = np.random.default_rng(1)
    n = 40_000
    return {
        "x": rng.normal(size=n),
        "y": rng.normal(size=n),
        "z": rng.uniform(0.0, 100.0, n),                          # continuous
        "cat": np.array(["a", "b", "c", "d"])[rng.integers(0, 4, n)],  # categorical
    }


def test_curve_rasterizes_to_line_density():
    n = 5000
    t = np.linspace(0, 10, n)
    curve = qv.Curve({"x": t, "y": np.sin(t)}, x="x", y="y", raster="datashader")
    r = rasterize_curve(curve, width=120, height=80)
    rgba, bounds = r.rgba, r.bounds
    assert rgba.shape == (80, 120, 4) and rgba.dtype == np.uint8
    assert rgba[..., 3].max() > 0  # the line painted pixels
    assert bounds[0] < bounds[2] and bounds[1] < bounds[3]


def _distinct_painted_colors(rgba) -> int:
    rgb = rgba[..., :3].reshape(-1, 3)
    painted = rgb[rgba[..., 3].reshape(-1) > 0]
    return len({tuple(c) for c in painted})


def test_categorical_color_by_blends_distinct_colors(typed_data):
    sc = qv.Scatter(typed_data, x="x", y="y", color_by="cat", raster="datashader")
    rgba = rasterize_scatter(sc, width=100, height=80).rgba
    # a per-category blend → more than one hue among the painted pixels
    assert _distinct_painted_colors(rgba) > 1


def test_numeric_color_by_changes_aggregation(typed_data):
    # color_by a numeric column aggregates as mean → a different raster than the
    # plain count-density one over the same points.
    base = qv.Scatter(typed_data, x="x", y="y", raster="datashader")
    valued = qv.Scatter(typed_data, x="x", y="y", color_by="z", raster="datashader")
    rgba_count = rasterize_scatter(base, width=100, height=80).rgba
    rgba_mean = rasterize_scatter(valued, width=100, height=80).rgba
    assert rgba_mean.shape == rgba_count.shape
    assert np.any(rgba_mean != rgba_count)


def test_categorical_via_points_color_key(typed_data):
    # explicit color_key path through the points primitive
    frame = _pandas(typed_data)
    rgba = rasterize_points(
        frame, "x", "y", width=80, height=60,
        color_by="cat", color_key={"a": "#ff0000", "b": "#00ff00", "c": "#0000ff", "d": "#ffffff"},
    ).rgba
    assert rgba.shape == (60, 80, 4) and _distinct_painted_colors(rgba) > 1


def test_curve_scale_routing():
    t = np.linspace(0, 1, 2000)
    data = {"x": t, "y": t**2}
    assert not pipeline._needs_rasterize(qv.Curve(data, x="x", y="y", raster="native"))
    assert pipeline._needs_rasterize(qv.Curve(data, x="x", y="y", raster="datashader"))


def test_resolve_transforms_curve_to_image():
    t = np.linspace(0, 1, 2000)
    curve = qv.Curve({"x": t, "y": t**2}, x="x", y="y", raster="datashader")
    image = pipeline.resolve_node(curve)
    assert isinstance(image, qv.Image)
    assert image.id == curve.id
    assert getattr(image, "_raster_source", None) is curve  # for re-aggregation (4b)


def test_rasterize_element_dispatches_by_glyph(typed_data):
    t = np.linspace(0, 5, 2000)
    curve = qv.Curve({"x": t, "y": np.cos(t)}, x="x", y="y", raster="datashader")
    scatter = qv.Scatter(typed_data, x="x", y="y", raster="datashader")
    # dispatch must match the per-element rasterizers exactly
    np.testing.assert_array_equal(
        rasterize_element(curve, width=60, height=40).rgba,
        rasterize_curve(curve, width=60, height=40).rgba,
    )
    np.testing.assert_array_equal(
        rasterize_element(scatter, width=60, height=40).rgba,
        rasterize_scatter(scatter, width=60, height=40).rgba,
    )


def test_numeric_color_by_keeps_dask_lazy(typed_data):
    dd = pytest.importorskip("dask.dataframe")
    pd = pytest.importorskip("pandas")
    ddf = dd.from_pandas(pd.DataFrame(typed_data), npartitions=4)
    frame = channel_frame(as_data_ref(ddf), {"x": "x", "y": "y", "color_by": "z"})
    assert type(frame).__module__.startswith(("dask", "dask_expr"))  # mean agg stays out-of-core


# ── async render through the View (Tier 2) ───────────────────────────────────
@pytest.mark.tier2
def test_datashaded_scatter_renders_async(data, qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    view = qv.View(qv.Scatter(data, x="x", y="y", raster="datashader"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle is None and view.loading  # aggregated off-thread
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    assert view.handle is not None


@pytest.mark.tier2
def test_datashaded_curve_renders_async(qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    t = np.linspace(0, 50, 200_000)
    data = {"x": t, "y": np.sin(t)}
    view = qv.View(qv.Curve(data, x="x", y="y", raster="datashader"), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.resize(500, 400)
    view.show()
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    vb = view.handle.plots[0].getViewBox()
    qtbot.waitUntil(lambda: getattr(vb, "_qtviz_rasters", None) is not None, timeout=4000)
