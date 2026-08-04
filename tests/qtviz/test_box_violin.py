"""0.4 increment 3 — BoxPlot + Violin ([D67], milestone-0.4 §4).

One stats core (`box_stats` / `kde`) shared by all three backends, so every
engine draws the *same* numbers — never Plotly's or matplotlib's house
statistics. Categories via `by=` share palette order with `color_by`.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core._stats import box_stats, kde  # noqa: E402
from qtviz.errors import ValidationError  # noqa: E402

rng = np.random.default_rng(11)
_VALUES = np.concatenate([rng.normal(10.0, 2.0, 200), [30.0, -8.0]])  # 2 clear outliers
_BY = {
    "score": np.concatenate([rng.normal(5.0, 1.0, 100), rng.normal(9.0, 1.0, 100)]),
    "cohort": np.array(["a"] * 100 + ["b"] * 100),
}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


# ── Tier-1: the stats core against numpy ground truth ────────────────────────
@pytest.mark.tier1
def test_box_stats_matches_numpy():
    st = box_stats(_VALUES)
    q1, med, q3 = np.percentile(_VALUES, [25, 50, 75])
    assert (st.q1, st.median, st.q3) == (q1, med, q3)
    iqr = q3 - q1
    inliers = _VALUES[(q1 - 1.5 * iqr <= _VALUES) & (q3 + 1.5 * iqr >= _VALUES)]
    assert st.lo_whisker == inliers.min() and st.hi_whisker == inliers.max()
    assert {30.0, -8.0} <= set(st.outliers)          # the planted outliers are flagged
    assert all(v < st.lo_whisker or v > st.hi_whisker for v in st.outliers)


@pytest.mark.tier1
def test_kde_is_a_density():
    grid, dens = kde(_VALUES)
    assert len(grid) == len(dens) == 128
    assert np.all(dens >= 0)
    area = np.trapezoid(dens, grid)
    assert 0.95 < area < 1.05                       # integrates to ~1
    assert grid[np.argmax(dens)] == pytest.approx(10.0, abs=1.5)  # mode near the mean


@pytest.mark.tier1
def test_box_violin_validation():
    with pytest.raises(ValidationError):
        qv.BoxPlot(_BY, value="score", by="cohort", color="#ff0000")  # exclusive
    with pytest.raises(ValidationError):
        qv.Violin({"v": [1.0]}, value="v", alpha=7.0)


# ── Tier-2: native rendering ─────────────────────────────────────────────────
@pytest.mark.tier2
def test_pyqtgraph_boxplot_draws_true_quartiles(qtbot):
    el = qv.BoxPlot(_BY, value="score", by="cohort")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    box_item = view.native(el.id)[0]                # [boxes, whisker-lines, outliers]
    a = _BY["score"][:100]
    q1, q3 = np.percentile(a, [25, 75])
    assert np.isclose(box_item.opts["y0"][0], q1)   # our stats, not the engine's
    assert np.isclose(box_item.opts["y1"][0], q3)
    labels = [lb.text for _s, lb in view.handle.plots[0]._qtviz_legend.items]
    assert labels == ["a", "b"]


@pytest.mark.tier2
def test_matplotlib_boxplot_uses_precomputed_stats(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    el = qv.BoxPlot(_BY, value="score", by="cohort")
    view = qv.View(el, backend="matplotlib")
    qtbot.addWidget(view)
    ax = view.handle.axes[0]
    med_a = float(np.median(_BY["score"][:100]))
    medians = [line.get_ydata()[0] for line in view.native(el.id)["medians"]]
    assert any(np.isclose(m, med_a) for m in medians)
    assert [t.get_text() for t in ax.get_xticklabels()][:2] == ["a", "b"]


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_violin_renders(backend, qtbot):
    if not _has(backend):
        pytest.skip(f"{backend} not registered")
    el = qv.Violin(_BY, value="score", by="cohort")
    view = qv.View(el, backend=backend)
    qtbot.addWidget(view)
    assert view.native(el.id) is not None


# ── Tier-1: webengine spec — precomputed, never Plotly's house stats ─────────
@pytest.mark.tier1
def test_webengine_box_trace_is_precomputed():
    from qtviz.backends.webengine import _figure

    el = qv.BoxPlot(_BY, value="score", by="cohort")
    fig = _figure.build_figure(el, qv.Theme.light())
    boxes = [t for t in fig["data"] if t["type"] == "box"]
    assert len(boxes) == 2                          # one per cohort
    a = _BY["score"][:100]
    q1, med, q3 = np.percentile(a, [25, 50, 75])
    assert boxes[0]["q1"] == [q1] and boxes[0]["median"] == [med] and boxes[0]["q3"] == [q3]
    assert "y" not in boxes[0]                      # no raw values → Plotly can't re-derive
    assert boxes[0]["name"] == "a" and boxes[0]["showlegend"] is True


@pytest.mark.tier1
def test_webengine_violin_is_a_polygon_not_plotly_violin():
    from qtviz.backends.webengine import _figure

    el = qv.Violin({"v": _VALUES}, value="v")
    fig = _figure.build_figure(el, qv.Theme.light())
    trace = fig["data"][0]
    assert trace["type"] == "scatter" and trace["fill"] == "toself"
    assert not any(t["type"] == "violin" for t in fig["data"])  # never Plotly's KDE
