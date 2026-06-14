"""dask adapter — out-of-core tabular + gridded data (milestone step 4).

The contract conformance for dask lives in test_adapter_conformance.py (the
parametrized suite). Here: the dask-specific laziness guarantees (no compute on
metadata/narrowing, projection via a single compute) and that lazy data renders
through the async View path.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
dd = pytest.importorskip("dask.dataframe")
da = pytest.importorskip("dask.array")
pd = pytest.importorskip("pandas")

from qtviz.data import as_data_ref  # noqa: E402

REF = {"a": np.arange(20.0), "b": np.arange(20.0) * 10.0, "c": np.arange(20.0) ** 2}


@pytest.fixture
def ddf():
    return dd.from_pandas(pd.DataFrame(REF), npartitions=3)


# ── laziness (Tier 1) ────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_metadata_and_narrowing_do_not_compute(ddf, monkeypatch):
    import dask

    calls = []
    real = dask.compute
    monkeypatch.setattr(dask, "compute", lambda *a, **k: (calls.append(1), real(*a, **k))[1])

    ref = as_data_ref(ddf)
    ref.schema()
    ref.select(["a"])
    ref.window(a=(0.0, 5.0))
    ref.fingerprint()
    assert not calls, "schema/select/window/fingerprint must not compute"

    ref.resolve_channels({"x": "a"})
    assert len(calls) == 1, "resolve computes once"


@pytest.mark.tier1
def test_resolves_channels_together_multipartition(ddf):
    ref = as_data_ref(ddf)
    out = ref.resolve_channels({"x": "a", "y": qv.col("a") + qv.col("b"), "z": lambda d: d["c"]})
    np.testing.assert_allclose(out["x"], REF["a"])
    np.testing.assert_allclose(out["y"], REF["a"] + REF["b"])
    np.testing.assert_allclose(out["z"], REF["c"])


@pytest.mark.tier1
def test_window_predicate_pushdown(ddf):
    ref = as_data_ref(ddf).window(a=(5.0, 8.0))
    assert ref.is_lazy
    np.testing.assert_allclose(ref.resolve_channels({"x": "a"})["x"], np.arange(5.0, 9.0))


@pytest.mark.tier1
def test_select_narrows_schema(ddf):
    assert set(as_data_ref(ddf).select(["a", "b"]).schema().names) == {"a", "b"}


@pytest.mark.tier1
def test_lazy_gridded_array_materializes(ddf):
    arr = da.from_array(np.outer(np.arange(4.0), np.arange(5.0)), chunks=(2, 5))
    ref = as_data_ref(arr)
    assert ref.is_lazy and ref.size() == 20
    eager = ref.materialize()
    assert not eager.is_lazy and np.asarray(eager.grid().values).shape == (4, 5)


# ── async render (Tier 2) ────────────────────────────────────────────────────
def _spin(qtbot, view, timeout=5000):
    qtbot.waitUntil(lambda: view.handle is not None, timeout=timeout)


@pytest.mark.tier2
def test_dask_scatter_renders_async(ddf, qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    view = qv.View(qv.Scatter(ddf, x="a", y="b"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle is None and view.loading  # resolved off-thread
    _spin(qtbot, view)
    assert view.handle is not None


@pytest.mark.tier2
def test_dask_image_renders_async(qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph backend not registered")
    arr = da.from_array(np.outer(np.hanning(30), np.hanning(40)), chunks=(15, 40))
    view = qv.View(qv.Image(arr, bounds=(0, 0, 40, 30)), backend="pyqtgraph")
    qtbot.addWidget(view)
    _spin(qtbot, view)
    assert view.handle is not None
