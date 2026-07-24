"""0.6 increment 3 — raster selection ([D78], milestone-0.6-live §3).

Brushing a datashaded view emitted nothing; now it emits a `SelectEvent` for
the *source* element — row indices when the source is eager, and always the
data-space bounds (the predicate that scales: a lazy source filters downstream
via `window(bounds)`). Closes the [D58] pixel→source-rows deferral for the
eager case.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("datashader")


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


def _cluster_data(n=4000):
    rng = np.random.default_rng(5)
    x = rng.uniform(0.0, 10.0, n)
    y = rng.uniform(0.0, 10.0, n)
    return {"x": x, "y": y}


def _shaded_view(qtbot, backend="pyqtgraph", data=None):
    data = data if data is not None else _cluster_data()
    el = qv.Scatter(data, x="x", y="y", scale="datashader")
    view = qv.View(el, backend=backend)
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)  # async resolve
    return view, el, data


@pytest.mark.tier2
def test_pyqtgraph_raster_brush_emits_source_indices(qtbot):
    view, el, data = _shaded_view(qtbot)
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0)
    view.handle.plots[0].getViewBox().select_bounds(2.0, 2.0, 4.0, 4.0)
    assert got
    ev = got[-1]
    assert ev.source_id == el.id                       # the SOURCE element, not the raster
    assert ev.bounds == (2.0, 2.0, 4.0, 4.0)
    expected = np.nonzero((data["x"] >= 2.0) & (data["x"] <= 4.0)
                          & (data["y"] >= 2.0) & (data["y"] <= 4.0))[0]
    assert ev.indices == expected.tolist()             # true row identity (eager)
    assert len(ev.indices) > 0


@pytest.mark.tier2
def test_matplotlib_raster_brush_emits_source_indices(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view, el, data = _shaded_view(qtbot, backend="matplotlib")
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0)
    view.handle.select_bounds(0, 2.0, 2.0, 4.0, 4.0)
    assert got and got[-1].source_id == el.id and len(got[-1].indices) > 0


@pytest.mark.tier2
def test_lazy_raster_brush_emits_bounds_only(qtbot):
    """Row identity on a lazy source would force a full scan per brush — the
    bounds ARE the selection; downstream filters by window(bounds) pushdown."""
    dd = pytest.importorskip("dask.dataframe")
    import pandas as pd

    pdf = pd.DataFrame(_cluster_data())
    ddf = dd.from_pandas(pdf, npartitions=4)
    el = qv.Scatter(ddf, x="x", y="y", scale="datashader")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0)
    view.handle.plots[0].getViewBox().select_bounds(2.0, 2.0, 4.0, 4.0)
    assert got
    assert got[-1].source_id == el.id
    assert got[-1].indices == []                       # no forced compute
    assert got[-1].bounds == (2.0, 2.0, 4.0, 4.0)      # the scalable predicate


@pytest.mark.tier2
def test_crossfilter_through_a_raster(qtbot):
    """The 0.6 story: brush the datashaded panel → a signal-driven linked panel
    re-renders with just the brushed rows."""
    data = _cluster_data()
    shaded = qv.Scatter(data, x="x", y="y", scale="datashader")
    selection = qv.signal(np.arange(len(data["x"])))
    detail = qv.derived(lambda: qv.Scatter(
        {"x": data["x"][selection.get()], "y": data["y"][selection.get()]},
        x="x", y="y"))
    view = qv.View(shaded, backend="pyqtgraph")
    detail_view = qv.View(detail)
    qtbot.addWidget(view)
    qtbot.addWidget(detail_view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    view.on(qv.SelectEvent, lambda e: selection.set(np.asarray(e.indices, dtype=int)),
            throttle_ms=0)
    view.handle.plots[0].getViewBox().select_bounds(2.0, 2.0, 4.0, 4.0)

    def detail_filtered():
        el_id = next(iter(detail_view.handle._natives))
        n = len(detail_view.handle._natives[el_id].getData()[0])
        return 0 < n < len(data["x"])

    qtbot.waitUntil(detail_filtered, timeout=3000)
