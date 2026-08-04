"""0.4 increment 2 — grouped/stacked Bars ([D68]) + a real Heatmap.aggregator
([D69]). The shared `core/_stats` helpers make every backend draw identical
numbers; the two "last value wins" TODOs close.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core._stats import grid_reduce, group_bars  # noqa: E402
from qtviz.errors import ValidationError  # noqa: E402

_GROUPED = {
    "quarter": np.array(["Q1", "Q1", "Q2", "Q2", "Q3"]),
    "region": np.array(["east", "west", "east", "west", "east"]),
    "sales": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


# ── Tier-1: the shared stats helpers ─────────────────────────────────────────
@pytest.mark.tier1
def test_group_bars_aligns_and_zero_fills():
    xs, gs, mat = group_bars(_GROUPED["quarter"], _GROUPED["sales"], _GROUPED["region"])
    assert list(xs) == ["Q1", "Q2", "Q3"] and list(gs) == ["east", "west"]
    assert np.allclose(mat, [[10.0, 30.0, 50.0],     # east
                             [20.0, 40.0, 0.0]])     # west: no Q3 row → 0


@pytest.mark.tier1
def test_group_bars_sums_duplicate_cells():
    xs, gs, mat = group_bars(["a", "a"], [1.0, 2.0], ["g", "g"])
    assert np.allclose(mat, [[3.0]])


@pytest.mark.tier1
def test_grid_reduce_aggregations():
    x = np.array([0.0, 0.0, 1.0, 0.0, 0.0])
    y = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
    z = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    xs, ys, mean = grid_reduce(x, y, z, "mean")
    assert list(xs) == [0.0, 1.0] and list(ys) == [0.0, 1.0]
    assert mean[0, 0] == 3.0                          # (2+4)/2 — not "last wins"
    assert mean[0, 1] == 6.0 and mean[1, 0] == 9.0    # (8+10)/2
    assert np.isnan(mean[1, 1])                       # empty (x=1, y=1) stays NaN
    assert grid_reduce(x, y, z, "sum")[2][0, 0] == 6.0
    assert grid_reduce(x, y, z, "count")[2][0, 0] == 2.0
    assert grid_reduce(x, y, z, "max")[2][0, 0] == 4.0
    assert grid_reduce(x, y, z, "min")[2][0, 0] == 2.0
    assert grid_reduce(x, y, z, "last")[2][0, 0] == 4.0   # the old behavior, kept


@pytest.mark.tier1
def test_bars_group_validation():
    with pytest.raises(ValidationError):
        qv.Bars(_GROUPED, x="quarter", y="sales", by="region", color="#ff0000")
    with pytest.raises(ValidationError):
        qv.Bars(_GROUPED, x="quarter", y="sales", mode="sideways")
    with pytest.raises(ValidationError):
        qv.Heatmap({"x": [1.0], "y": [1.0], "z": [1.0]}, x="x", y="y", z="z",
                   aggregator="median")


# ── Tier-2: native rendering ─────────────────────────────────────────────────
@pytest.mark.tier2
@pytest.mark.parametrize("mode", ["grouped", "stacked"])
def test_pyqtgraph_group_bars_one_item_per_group(mode, qtbot):
    el = qv.Bars(_GROUPED, x="quarter", y="sales", by="region", mode=mode)
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    items = view.native(el.id)
    assert isinstance(items, list) and len(items) == 2      # east + west
    # group legend drawn via the color-mapping path
    labels = [lb.text for _s, lb in view.handle.plots[0]._qtviz_legend.items]
    assert labels == ["east", "west"]


@pytest.mark.tier2
def test_pyqtgraph_stacked_bases(qtbot):
    el = qv.Bars(_GROUPED, x="quarter", y="sales", by="region", mode="stacked")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    east, west = view.native(el.id)
    assert np.allclose(east.opts["y0"], [0.0, 0.0, 0.0])
    assert np.allclose(west.opts["y0"], [10.0, 30.0, 50.0])  # stacked on east
    assert np.allclose(west.opts["y1"], [30.0, 70.0, 50.0])  # Q3 west is empty (0)


@pytest.mark.tier2
def test_matplotlib_grouped_and_stacked(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    el = qv.Bars(_GROUPED, x="quarter", y="sales", by="region", mode="stacked")
    view = qv.View(el, backend="matplotlib")
    qtbot.addWidget(view)
    ax = view.handle.axes[0]
    heights = sorted(p.get_height() for p in ax.patches)
    assert heights == [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    # stacked: west's Q1 bar starts at east's height
    west_q1 = [p for p in ax.patches if p.get_y() == 10.0]
    assert west_q1 and west_q1[0].get_height() == 20.0
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["east", "west"]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["Q1", "Q2", "Q3"]


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_heatmap_aggregator_means_not_last(backend, qtbot):
    if not _has(backend):
        pytest.skip(f"{backend} not registered")
    data = {"x": [0.0, 0.0, 1.0], "y": [0.0, 0.0, 0.0], "z": [2.0, 4.0, 6.0]}
    el = qv.Heatmap(data, x="x", y="y", z="z")            # default aggregator="mean"
    view = qv.View(el, backend=backend)
    qtbot.addWidget(view)
    artist = view.native(el.id)
    grid = np.asarray(artist.image if backend == "pyqtgraph" else artist.get_array())
    assert 3.0 in grid.ravel()                            # (2+4)/2, not 4.0 ("last")


# ── Tier-1: webengine figure spec ────────────────────────────────────────────
@pytest.mark.tier1
def test_webengine_group_bars_traces_and_barmode():
    from qtviz.backends.webengine import _figure

    el = qv.Bars(_GROUPED, x="quarter", y="sales", by="region", mode="stacked")
    fig = _figure.build_figure(el, qv.Theme.light())
    assert fig["layout"]["barmode"] == "stack"
    assert [t["name"] for t in fig["data"]] == ["east", "west"]
    assert all(t["showlegend"] for t in fig["data"])
    east = fig["data"][0]
    assert list(east["x"]) == ["Q1", "Q2", "Q3"] and np.allclose(east["y"], [10, 30, 50])


@pytest.mark.tier1
def test_webengine_heatmap_grid_uses_aggregator():
    from qtviz.backends.webengine import _figure

    data = {"x": [0.0, 0.0, 1.0], "y": [0.0, 0.0, 0.0], "z": [2.0, 4.0, 6.0]}
    fig = _figure.build_figure(qv.Heatmap(data, x="x", y="y", z="z", aggregator="sum"),
                               qv.Theme.light())
    assert fig["data"][0]["z"][0][0] == 6.0               # 2+4 summed into the cell
