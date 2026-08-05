"""Tier-2 — async materialize orchestration (milestone-data-core step 2, D13).

Lazy data is resolved off the GUI thread; the View keeps a placeholder/last
render while loading, drops stale results by build-id, and surfaces errors.
Exercised with a synthetic lazy stub (no dask) so the async path is
deterministic.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("pyqtgraph")

from qtviz.data.accessor import resolve_accessor  # noqa: E402
from qtviz.data.ref import Schema, TabularRef  # noqa: E402

pytestmark = pytest.mark.tier2


class LazyStubRef(TabularRef):
    """A lazy tabular ref whose resolve can be gated, recording the thread it
    ran on. Stands in for dask/zarr without the dependency."""

    is_lazy = True

    def __init__(self, cols, gate: threading.Event | None = None) -> None:
        self._cols = {k: np.asarray(v, dtype="float64") for k, v in cols.items()}
        self._gate = gate
        self.resolved_thread: str | None = None
        self.calls = 0

    def schema(self) -> Schema:
        return Schema(names=tuple(self._cols), kind="tabular")

    def size(self):
        return len(next(iter(self._cols.values())))

    def fingerprint(self):
        return id(self._cols)

    def native(self):
        return self._cols

    def resolve_channels(self, channels, *, who=None):
        if self._gate is not None:
            self._gate.wait()
        self.calls += 1
        self.resolved_thread = threading.current_thread().name
        return {r: resolve_accessor(a, columns=self._cols, native=self._cols)
                for r, a in channels.items()}


def _scatter(ref):
    return qv.Scatter(ref, x="a", y="b")


@pytest.fixture
def make_view(qtbot):
    import qtviz.backends as B

    if "pyqtgraph" not in B.list_available():
        pytest.skip("pyqtgraph backend not registered")

    def make(root):
        view = qv.View(root, backend="pyqtgraph")
        qtbot.addWidget(view)
        return view

    return make


def test_eager_is_synchronous(make_view):
    view = make_view(_scatter({"a": np.arange(5.0), "b": np.arange(5.0)}))
    assert view.handle is not None  # eager → rendered immediately, no async
    assert not view.loading


def test_lazy_renders_off_thread(make_view, qtbot):
    stub = LazyStubRef({"a": np.arange(10), "b": np.arange(10) ** 2})
    view = make_view(_scatter(stub))
    assert view.handle is None and view.loading  # placeholder while resolving
    qtbot.waitUntil(lambda: view.handle is not None, timeout=5000)
    assert not view.loading
    assert stub.resolved_thread and stub.resolved_thread != threading.main_thread().name


def test_resolve_error_is_surfaced(make_view, qtbot):
    class BadRef(LazyStubRef):
        def resolve_channels(self, channels, *, who=None):
            raise RuntimeError("boom")

    view = make_view(_scatter(BadRef({"a": [1.0, 2.0], "b": [1.0, 2.0]})))
    qtbot.waitUntil(lambda: view._error is not None, timeout=5000)
    assert view.handle is None


def test_stale_build_is_dropped(make_view, qtbot):
    gate = threading.Event()
    blocked = LazyStubRef({"a": np.arange(5), "b": np.arange(5)}, gate=gate)
    fresh = LazyStubRef({"a": np.arange(7), "b": np.arange(7)})

    view = make_view(_scatter(blocked))     # build N — stuck on the gate
    view.set_root(_scatter(fresh))          # build N+1 — resolves immediately
    qtbot.waitUntil(lambda: view.handle is not None, timeout=5000)
    current = view.handle                   # the fresh (N+1) render

    gate.set()                              # let the stale (N) resolve finish
    qtbot.waitUntil(lambda: blocked.calls > 0, timeout=5000)
    qtbot.wait(50)                          # give a stale install a chance to (wrongly) happen
    assert view.handle is current           # the stale result was dropped
