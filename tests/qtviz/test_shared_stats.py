"""Parity program increment 2 — shared-stats honesty ([D92]/[D93]).

One histogram binning engine for every backend (numpy rule strings pass
through instead of collapsing to "auto"), `Heatmap` drawn in real data
coordinates on the native backends (webengine already was — and pg's
heatmap was transposed under its col-major default), and pyqtgraph's
parity debts paid: Image/Heatmap colormap, ErrorBars color + direction.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_VALS = list(np.random.default_rng(3).normal(size=200))
_HTABLE = {"v": _VALS}
_GRID = {  # 3 x-centers (0,1,2) x 2 y-centers (0,10), distinct values
    "x": [0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
    "y": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0],
    "z": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_histogram_bins_validation():
    from qtviz.errors import ValidationError

    qv.Histogram(_HTABLE, value="v", bins="fd")  # numpy rule: ok
    qv.Histogram(_HTABLE, value="v", bins=12)
    with pytest.raises(ValidationError):
        qv.Histogram(_HTABLE, value="v", bins="banana")
    with pytest.raises(ValidationError):
        qv.Histogram(_HTABLE, value="v", bins=0)


@pytest.mark.tier1
def test_core_histogram_matches_numpy():
    from qtviz.core._stats import histogram

    counts, edges = histogram(_VALS, "sturges")
    exp_counts, exp_edges = np.histogram(np.asarray(_VALS), bins="sturges")
    assert np.array_equal(counts, exp_counts) and np.array_equal(edges, exp_edges)


@pytest.mark.tier1
def test_webengine_histogram_is_prebinned():
    """[D93]: webengine stops letting Plotly bin client-side — the trace is a
    pre-binned bar built from the shared core binning."""
    from qtviz.backends.webengine import _figure

    el = qv.Histogram(_HTABLE, value="v", bins="sturges")
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    exp_counts, exp_edges = np.histogram(np.asarray(_VALS), bins="sturges")
    assert trace["type"] == "bar"
    assert np.allclose(trace["y"], exp_counts)
    assert np.allclose(trace["width"], np.diff(exp_edges))


@pytest.mark.tier1
def test_webengine_image_colormap_and_interpolation():
    from qtviz.backends.webengine import _figure

    el = qv.Image(np.arange(12.0).reshape(3, 4), bounds=(0, 0, 4, 3),
                  colormap="plasma", interpolation="nearest")
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["colorscale"] == "Plasma"
    assert trace["zsmooth"] is False
    el2 = qv.Image(np.arange(12.0).reshape(3, 4), bounds=(0, 0, 4, 3))
    assert _figure.build_figure(el2, qv.Theme.light())["data"][0]["zsmooth"] == "best"


@pytest.mark.tier1
def test_webengine_heatmap_colormap():
    from qtviz.backends.webengine import _figure

    el = qv.Heatmap(_GRID, x="x", y="y", z="z", colormap="cividis")
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["colorscale"] == "Cividis"


@pytest.mark.tier1
def test_webengine_unknown_colormap_warns_and_falls_back():
    from qtviz.backends.webengine import _figure
    from qtviz.errors import QtvizWarning

    el = qv.Heatmap(_GRID, x="x", y="y", z="z", colormap="gist_ncar")
    with pytest.warns(QtvizWarning):
        trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["colorscale"] == "Viridis"


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_histogram_honors_rule_strings(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Histogram(_HTABLE, value="v", bins="sturges")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    exp_counts, _ = np.histogram(np.asarray(_VALS), bins="sturges")
    heights = [p.get_height() for p in handle.axes[0].patches]
    assert np.allclose(sorted(heights), sorted(exp_counts))


@pytest.mark.tier2
def test_mpl_heatmap_data_coordinates(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Heatmap(_GRID, x="x", y="y", z="z")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    artist = handle.native(el.id)
    # centers 0,1,2 → x extent ±half-cell; centers 0,10 → y extent ±5
    assert tuple(artist.get_extent()) == (-0.5, 2.5, -5.0, 15.0)


@pytest.mark.tier2
def test_mpl_heatmap_categorical_ticks(qtbot):
    pytest.importorskip("matplotlib")
    data = {"x": ["a", "b", "a", "b"], "y": [0.0, 0.0, 1.0, 1.0],
            "z": [1.0, 2.0, 3.0, 4.0]}
    handle = _backend("matplotlib").render(
        qv.Heatmap(data, x="x", y="y", z="z"), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["a", "b"]


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_histogram_honors_rule_strings(qtbot):
    el = qv.Histogram(_HTABLE, value="v", bins="sturges")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    exp_counts, _ = np.histogram(np.asarray(_VALS), bins="sturges")
    assert len(np.asarray(handle.native(el.id).opts["height"])) == len(exp_counts)


@pytest.mark.tier2
def test_pg_heatmap_data_coordinates_and_orientation(qtbot):
    el = qv.Heatmap(_GRID, x="x", y="y", z="z")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert item.axisOrder == "row-major"  # was col-major → transposed vs mpl/web
    rect = item.mapRectToParent(item.boundingRect())
    assert (rect.left(), rect.right()) == (-0.5, 2.5)
    assert (rect.top(), rect.bottom()) == (-5.0, 15.0)


@pytest.mark.tier2
def test_pg_heatmap_colormap_applied(qtbot):
    el = qv.Heatmap(_GRID, x="x", y="y", z="z", colormap="plasma")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id).lut is not None


@pytest.mark.tier2
def test_pg_image_colormap_applied(qtbot):
    el = qv.Image(np.arange(12.0).reshape(3, 4), bounds=(0, 0, 4, 3),
                  colormap="plasma")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id).lut is not None


@pytest.mark.tier2
def test_pg_errorbars_direction_and_color(qtbot):
    data = {"x": [0.0, 1.0], "y": [1.0, 2.0], "err": [0.1, 0.2]}
    el = qv.ErrorBars(data, x="x", y="y", err="err", direction="both",
                      color="#ff0000")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    opts = handle.native(el.id).opts
    assert opts.get("right") is not None and opts.get("top") is not None
    assert opts["pen"].color().name() == "#ff0000"


@pytest.mark.tier2
def test_pg_errorbars_x_only(qtbot):
    data = {"x": [0.0, 1.0], "y": [1.0, 2.0], "err": [0.1, 0.2]}
    el = qv.ErrorBars(data, x="x", y="y", err="err", direction="x")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    opts = handle.native(el.id).opts
    assert opts.get("left") is not None and opts.get("top") is None
