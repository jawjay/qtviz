"""Datashader aggregate/shade split (roadmap §8.5, C1; [D47]).

Shading used to be welded to aggregation in `_aggregate_and_shade`, theme-less and
legend-less. This splits the two: `aggregate_element` produces a theme-free
`Aggregate` (the raw datashader agg + bounds + the [D46] hover view), and
`shade_aggregate` turns that into a shaded `RasterResult`. C1 is a *pure refactor* —
the golden tests below pin the pre-refactor rgba so output cannot drift.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("datashader")

from qtviz.ext.datashader import (  # noqa: E402
    Aggregate,
    RasterAggregate,
    RasterResult,
    aggregate_element,
    rasterize_element,
    rasterize_scatter,
    shade_aggregate,
)

pytestmark = pytest.mark.tier1


def _sha(rgba) -> str:
    return hashlib.sha256(rgba.tobytes()).hexdigest()


def _count_scatter():
    rng = np.random.default_rng(42)
    n = 20_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n)}
    return qv.Scatter(data, x="x", y="y")


def _sine_curve():
    t = np.linspace(0, 10, 4000)
    return qv.Curve({"x": t, "y": np.sin(t)}, x="x", y="y")


# ── golden regression: the refactor must not change a single pixel ───────────
# Count / line aggregation is integer and deterministic, so the rgba is
# bit-stable across platforms and datashader versions with a pinned frame.
def test_golden_count_scatter_rgba_unchanged():
    r = rasterize_scatter(_count_scatter(), width=64, height=48,
                          x_range=(-4, 4), y_range=(-4, 4))
    assert _sha(r.rgba) == "246f5ce809154279bf3aa215dcc685868f08d8f7d822b590a1bad427f293ac73"
    assert r.bounds == (-3.9375, -3.9166666666666665, 3.9375, 3.9166666666666665)


def test_golden_curve_rgba_unchanged():
    r = rasterize_element(_sine_curve(), width=64, height=48,
                          x_range=(0, 10), y_range=(-1, 1))
    assert _sha(r.rgba) == "882a96a2b01b8a50c5bedbcb7995941b22d0c1707f4193c3d84938e192748599"


# ── new API: aggregate (theme-free) ↔ shade (theme-aware) ────────────────────
def test_aggregate_element_returns_unshaded_aggregate():
    agg = aggregate_element(_count_scatter(), width=64, height=48,
                            x_range=(-4, 4), y_range=(-4, 4))
    assert isinstance(agg, Aggregate)
    assert agg.kind == "count"
    assert agg.categories is None
    assert isinstance(agg.aggregate, RasterAggregate)  # [D46] hover view preserved
    assert agg.agg is not None  # the raw xarray agg, for faithful re-shading
    assert agg.bounds[0] < agg.bounds[2] and agg.bounds[1] < agg.bounds[3]


def test_shade_of_aggregate_equals_rasterize():
    # decomposition consistency: shade(aggregate(x)) == rasterize(x), pixel-exact
    el = _count_scatter()
    kw = dict(width=64, height=48, x_range=(-4, 4), y_range=(-4, 4))
    shaded = shade_aggregate(aggregate_element(el, **kw))
    assert isinstance(shaded, RasterResult)
    np.testing.assert_array_equal(shaded.rgba, rasterize_scatter(el, **kw).rgba)


def test_aggregate_categorical_carries_category_labels():
    rng = np.random.default_rng(1)
    n = 10_000
    data = {
        "x": rng.normal(size=n), "y": rng.normal(size=n),
        "cat": np.array(["a", "b", "c"])[rng.integers(0, 3, n)],
    }
    agg = aggregate_element(qv.Scatter(data, x="x", y="y", color_by="cat"),
                            width=40, height=30)
    assert agg.kind == "category"
    assert set(agg.categories) == {"a", "b", "c"}


def test_aggregate_numeric_color_by_is_mean():
    rng = np.random.default_rng(2)
    n = 8_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n),
            "z": rng.uniform(0, 100, n)}
    agg = aggregate_element(qv.Scatter(data, x="x", y="y", color_by="z"),
                            width=40, height=30)
    assert agg.kind == "mean"
    assert agg.categories is None


# ── C2: theme-driven colors ([D50]) ──────────────────────────────────────────
def _categorical_agg():
    rng = np.random.default_rng(7)
    n = 12_000
    data = {
        "x": rng.normal(size=n), "y": rng.normal(size=n),
        "cat": np.array(["a", "b", "c"])[rng.integers(0, 3, n)],
    }
    return aggregate_element(qv.Scatter(data, x="x", y="y", color_by="cat"),
                             width=50, height=40)


def test_shade_palette_changes_categorical_colors():
    from qtviz.core.palette import Palette

    agg = _categorical_agg()
    a = shade_aggregate(agg, palette=Palette.from_hex(["#ff0000", "#00ff00", "#0000ff"]))
    b = shade_aggregate(agg, palette=Palette.from_hex(["#ffff00", "#00ffff", "#ff00ff"]))
    assert np.any(a.rgba != b.rgba)  # the theme palette actually drives the colors


def test_category_swatches_match_native_assignment():
    # one source of truth: the i-th sorted category gets palette[i] both natively
    # (map_colors) and in the raster color key (category_swatches).
    from qtviz.core.encoding import category_swatches, map_colors
    from qtviz.core.palette import Palette

    pal = Palette.from_hex(["#111111", "#222222", "#333333", "#444444"])
    cats = np.array(["a", "b", "c", "a", "b"])
    native_rgba, _ = map_colors(cats, palette=pal, kind="categorical")
    swatches = category_swatches(["a", "b", "c"], pal)  # sorted/unique order
    # native row 0 is "a" → palette[0]; swatches[0] is the same color
    assert swatches[0].rgba == tuple(native_rgba[0])
    assert swatches[1].rgba == tuple(native_rgba[1])  # "b" → palette[1]


def test_explicit_color_key_overrides_palette():
    from qtviz.core.palette import Palette

    agg = _categorical_agg()
    keyed = shade_aggregate(agg, color_key={"a": "#ff0000", "b": "#00ff00", "c": "#0000ff"})
    paletted = shade_aggregate(agg, palette=Palette.from_hex(["#ff0000", "#00ff00", "#0000ff"]))
    # an explicit datashader color_key and the equivalent palette agree
    np.testing.assert_array_equal(keyed.rgba, paletted.rgba)


# ── C2: the theme reaches a rendered raster (wiring) ─────────────────────────
def _painted_colors(image) -> set:
    arr = np.asarray(image)
    rgb = arr[..., :3].reshape(-1, 3)
    alpha = arr[..., 3].reshape(-1)
    return {tuple(int(v) for v in c) for c in rgb[alpha > 0]}


def _first_image_item(handle):
    import pyqtgraph as pg

    for plot in handle.plots:
        for it in plot.items:
            if isinstance(it, pg.ImageItem):
                return it
    raise AssertionError("no ImageItem in the rendered handle")


@pytest.mark.tier2
def test_rendered_raster_uses_theme_palette(qtbot):
    from qtviz.core.palette import Palette
    from qtviz.core.theme import Theme

    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    rng = np.random.default_rng(3)
    n = 30_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n),
            "cat": np.array(["a", "b", "c"])[rng.integers(0, 3, n)]}
    node = qv.Scatter(data, x="x", y="y", color_by="cat", raster="datashader")

    custom = Theme(palette=Palette.from_hex(["#ff0000", "#00ff00", "#0000ff"]))
    themed = qv.View(node, backend="pyqtgraph", theme=custom)
    default = qv.View(node, backend="pyqtgraph")  # default category10
    for v in (themed, default):
        qtbot.addWidget(v)
        qtbot.waitUntil(lambda v=v: v.handle is not None, timeout=8000)

    # the raster's painted colors track the View's Theme, not a fixed default
    assert _painted_colors(_first_image_item(themed.handle).image) \
        != _painted_colors(_first_image_item(default.handle).image)


# ── C3: legends / colorbars ([D48]) ──────────────────────────────────────────
def _value_agg(kind_col="z"):
    rng = np.random.default_rng(11)
    n = 9_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n),
            "z": rng.uniform(10.0, 50.0, n)}
    return aggregate_element(qv.Scatter(data, x="x", y="y", color_by="z"),
                             width=40, height=30)


def test_categorical_shade_emits_category_legend():
    from qtviz.core.palette import Palette

    pal = Palette.from_hex(["#ff0000", "#00ff00", "#0000ff"])
    res = shade_aggregate(_categorical_agg(), palette=pal, title="cat")
    lg = res.legend
    assert lg is not None and lg.kind == "categorical" and lg.title == "cat"
    labels = [label for label, _ in lg.entries]
    assert labels == ["a", "b", "c"]
    assert lg.entries[0][1].hex() == "#ff0000"  # category "a" → palette[0]


def test_value_shade_emits_linear_colorbar():
    res = shade_aggregate(_value_agg(), title="z")
    lg = res.legend
    assert lg.kind == "continuous" and lg.linear is True  # value agg → truthful linear bar
    assert 10.0 <= lg.vmin <= lg.vmax <= 50.0  # mean of z stays within its range
    assert lg.title == "z"


def test_count_shade_emits_nonlinear_density_legend():
    agg = aggregate_element(_count_scatter(), width=64, height=48)
    lg = shade_aggregate(agg).legend
    assert lg.kind == "continuous" and lg.linear is False  # eq_hist density → endpoints only
    assert lg.title == "density"


@pytest.mark.tier2
def test_rendered_categorical_raster_draws_legend(qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    rng = np.random.default_rng(5)
    n = 20_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n),
            "cat": np.array(["a", "b", "c"])[rng.integers(0, 3, n)]}
    view = qv.View(qv.Scatter(data, x="x", y="y", color_by="cat", raster="datashader"),
                   backend="pyqtgraph")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    plot = view.handle.plots[0]
    assert getattr(plot, "_qtviz_legend", None) is not None  # a category key was drawn


@pytest.mark.tier2
def test_add_legend_replaces_not_stacks(qtbot):
    import pyqtgraph as pg

    from qtviz.backends.pyqtgraph._legend import add_legend
    from qtviz.core.color import Color
    from qtviz.core.encoding import Legend
    from qtviz.core.theme import Theme

    win = pg.GraphicsLayoutWidget()
    qtbot.addWidget(win)
    plot = win.addPlot()
    theme = Theme.light()
    add_legend(plot, Legend(kind="categorical", entries=(("a", Color("#ff0000")),)), theme)
    add_legend(plot, Legend(kind="categorical",
                            entries=(("a", Color("#00ff00")), ("b", Color("#0000ff")))), theme)
    # re-drawing must replace the old legend, not accumulate (Risk #1, [D48])
    legends = [it for it in plot.scene().items() if isinstance(it, pg.LegendItem)]
    assert len(legends) == 1


# ── C4: aggregation surface ([D49]) ──────────────────────────────────────────
def _single_pixel_agg(agg):
    # all points fall in one 1×1 pixel, so the reduction is the value at [0, 0]
    data = {"x": [0.5, 0.5, 0.5], "y": [0.5, 0.5, 0.5], "z": [10.0, 50.0, 30.0]}
    return aggregate_element(
        qv.Scatter(data, x="x", y="y", color_by="z", agg=agg, raster="datashader"),
        width=1, height=1, x_range=(0, 1), y_range=(0, 1),
    )


def test_agg_max_takes_pixel_maximum():
    agg = _single_pixel_agg("max")
    assert agg.kind == "max"
    assert float(agg.aggregate.values[0, 0]) == 50.0


def test_agg_sum_and_min_and_mean():
    assert float(_single_pixel_agg("sum").aggregate.values[0, 0]) == 90.0
    assert float(_single_pixel_agg("min").aggregate.values[0, 0]) == 10.0
    assert float(_single_pixel_agg("mean").aggregate.values[0, 0]) == 30.0


def test_agg_auto_is_count_without_color_by():
    data = {"x": [0.5, 0.5, 0.5], "y": [0.5, 0.5, 0.5]}
    agg = aggregate_element(qv.Scatter(data, x="x", y="y", raster="datashader"),
                            width=1, height=1, x_range=(0, 1), y_range=(0, 1))
    assert agg.kind == "count"
    assert float(agg.aggregate.values[0, 0]) == 3.0


def test_value_agg_requires_color_by():
    from qtviz.errors import ValidationError

    with pytest.raises(ValidationError):
        qv.Scatter({"x": [1.0], "y": [2.0]}, x="x", y="y", agg="mean", raster="datashader")


def test_agg_requires_datashader_scale():
    from qtviz.errors import ValidationError

    with pytest.raises(ValidationError):  # agg under the default raster="native"
        qv.Scatter({"x": [1.0], "y": [2.0]}, x="x", y="y", color_by="x", agg="max")


def test_value_agg_legend_is_linear_with_title():
    res = shade_aggregate(_single_pixel_agg("max"), title="z")
    assert res.legend.kind == "continuous" and res.legend.linear is True
    assert res.legend.title == "z"


# ── C5: webengine raster theme parity ────────────────────────────────────────
def test_webengine_raster_uses_theme_palette():
    from qtviz.backends.webengine._figure import _image_trace
    from qtviz.core.palette import Palette
    from qtviz.core.theme import Theme
    from qtviz.data import pipeline

    rng = np.random.default_rng(9)
    n = 12_000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n),
            "cat": np.array(["a", "b", "c"])[rng.integers(0, 3, n)]}
    scatter = qv.Scatter(data, x="x", y="y", color_by="cat", raster="datashader")
    image = pipeline.resolve_node(scatter)

    z1 = _image_trace(image, Theme(palette=Palette.from_hex(["#ff0000", "#00ff00", "#0000ff"])), 0)
    z2 = _image_trace(image, Theme(palette=Palette.from_hex(["#ffff00", "#00ffff", "#ff00ff"])), 0)
    # the webengine raster shades with the View's Theme, like the native backends (C5)
    assert np.any(np.asarray(z1[0]["z"]) != np.asarray(z2[0]["z"]))
