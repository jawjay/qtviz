"""Wave 1.4 — [D115] `Stem`: lollipop/stem plots as a first-class data element.

Per-point vertical segments `(x, baseline) → (x, y)` computed once in core
([D110]), drawn as ONE pair-connected polyline + a marker layer per backend
(never one item per stem): pg `PlotCurveItem(connect="pairs")` + scatter
heads, mpl `LineCollection` + scatter (not `ax.stem` — its container fights
the handle contract), Plotly a NaN-gapped line trace + a marker trace. Heads
pick like Scatter points; the element takes a palette slot and a legend
entry like any series.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": np.array([0.0, 1.0, 2.0, 3.0]),
      "y": np.array([2.0, -1.0, 3.0, 0.5])}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation_and_defaults():
    from qtviz.errors import ValidationError

    el = qv.Stem(_T, x="x", y="y")
    assert el.baseline == 0.0 and el.marker == "circle"
    qv.Stem(_T, x="x", y="y", baseline=1.0, marker="diamond", line_width=2.0)
    with pytest.raises(ValidationError):
        qv.Stem(_T, x="x", y="y", alpha=1.5)
    with pytest.raises(TypeError):
        qv.Stem(_T, x="x", y="y", x2="nope")  # unknown option
    with pytest.raises((ValidationError, TypeError)):
        qv.Stem(_T, x="x")                    # y required


@pytest.mark.tier1
def test_core_segments_connect_baseline_to_heads():
    from qtviz.core._geometry import stem_segments

    sx, sy = stem_segments(_T["x"], _T["y"], baseline=0.5)
    assert len(sx) == 8                              # 2 points per stem, pairs
    assert list(sx[:4]) == [0.0, 0.0, 1.0, 1.0]
    assert list(sy[:4]) == [0.5, 2.0, 0.5, -1.0]     # (x, baseline) → (x, y)


@pytest.mark.tier1
def test_legend_entry_like_any_series():
    theme = qv.Theme.light()
    e = qv.Stem(_T, x="x", y="y", label="events").legend_entry(theme, 1)
    assert e.label == "events" and e.swatch == theme.palette[1]
    assert qv.Stem(_T, x="x", y="y").legend_entry(theme) is None


@pytest.mark.tier1
def test_webengine_stem_traces():
    from qtviz.backends.webengine import _figure

    traces = _figure.build_figure(
        qv.Stem(_T, x="x", y="y", label="ev"), qv.Theme.light())["data"]
    assert len(traces) == 2
    lines, heads = traces
    assert lines["mode"] == "lines"
    assert len(lines["x"]) == 4 * 3                  # x, x, NaN gap per stem
    assert heads["mode"] == "markers"
    assert list(heads["x"]) == list(_T["x"])
    assert heads["showlegend"] is True and heads["name"] == "ev"


@pytest.mark.tier2
def test_pg_one_pairs_item_plus_heads(qtbot):
    import pyqtgraph as pg

    el = qv.Stem(_T, x="x", y="y")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    stems, heads = handle.native(el.id)
    assert isinstance(stems, pg.PlotCurveItem)       # ONE item for all stems
    assert stems.opts["connect"] == "pairs"
    assert isinstance(heads, pg.ScatterPlotItem)
    hx, hy = heads.getData()
    assert np.allclose(hx, _T["x"]) and np.allclose(hy, _T["y"])
    # heads are brush-selectable / pickable like Scatter points
    vb = handle.plots[0].getViewBox()
    assert any(sid == el.id for sid, _x, _y in vb._selectables)


@pytest.mark.tier2
def test_mpl_linecollection_plus_scatter(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.collections import LineCollection

    el = qv.Stem(_T, x="x", y="y", baseline=1.0)
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    stems, heads = handle.native(el.id)
    assert isinstance(stems, LineCollection)
    segs = stems.get_segments()
    assert len(segs) == 4
    assert segs[0][0][1] == 1.0                      # starts at the baseline
    assert heads.get_offsets().shape == (4, 2)


@pytest.mark.tier2
def test_backends_draw_identical_stems(qtbot):
    """[D110]: matplotlib segments and pg pair-arrays describe the same lines."""
    pytest.importorskip("matplotlib")
    el = qv.Stem(_T, x="x", y="y")
    h1 = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    h2 = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    mpl_segs = np.asarray(h1.native(el.id)[0].get_segments())  # (n, 2, 2)
    px, py = h2.native(el.id)[0].getData()
    pg_segs = np.stack([px.reshape(-1, 2), py.reshape(-1, 2)], axis=-1)
    assert np.allclose(mpl_segs, pg_segs)
