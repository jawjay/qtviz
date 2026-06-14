"""Reactive layer conformance (spec §9; D38–D40).

The Signal/derived/effect/batch core is pure (no QApplication needed — `set` runs
synchronously when there's no GUI thread to marshal to), so it's tier-1. View-root
binding, cross-thread `set`, and the crossfilter payoff are tier-2.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")


# ── core: Signal ──────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_signal_get_set():
    s = qv.signal(1)
    assert s.get() == 1
    s.set(2)
    assert s.get() == 2


@pytest.mark.tier1
def test_signal_subscribe_fires_then_disposes():
    s = qv.signal(0)
    seen: list = []
    d = s.subscribe(seen.append)
    s.set(5)
    s.set(7)
    assert seen == [5, 7]
    d.dispose()
    s.set(9)
    assert seen == [5, 7]            # no delivery after dispose
    d.dispose()                      # idempotent


# ── core: derived ─────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_derived_auto_tracks_dependencies():
    a, b = qv.signal(2), qv.signal(3)
    d = qv.derived(lambda: a.get() + b.get())
    assert d.get() == 5
    a.set(10)
    assert d.get() == 13
    b.set(0)
    assert d.get() == 10


@pytest.mark.tier1
def test_derived_is_memoized():
    a = qv.signal(1)
    calls: list = []

    def compute():
        calls.append(1)
        return a.get() * 2

    d = qv.derived(compute)
    assert d.get() == 2
    d.get()
    d.get()
    assert len(calls) == 1          # not recomputed without a dependency change
    a.set(5)
    assert d.get() == 10
    assert len(calls) == 2


@pytest.mark.tier1
def test_derived_of_derived():
    a = qv.signal(1)
    d1 = qv.derived(lambda: a.get() + 1)
    d2 = qv.derived(lambda: d1.get() * 10)
    assert d2.get() == 20
    a.set(4)
    assert d2.get() == 50


# ── core: effect ──────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_effect_runs_immediately_and_on_change():
    a = qv.signal(1)
    seen: list = []
    e = qv.effect(lambda: seen.append(a.get()))
    assert seen == [1]              # runs once immediately
    a.set(2)
    assert seen == [1, 2]
    e.dispose()
    a.set(3)
    assert seen == [1, 2]           # stopped


# ── core: batch ───────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_batch_coalesces_writes():
    a, b = qv.signal(0), qv.signal(0)
    runs: list = []
    qv.effect(lambda: runs.append((a.get(), b.get())))
    assert runs == [(0, 0)]
    qv.batch(lambda: (a.set(1), b.set(2)))
    assert runs == [(0, 0), (1, 2)]  # one re-run, not two


# ── integration: View-root binding (D38/D40) ─────────────────────────────────
@pytest.mark.tier2
def test_view_rerenders_when_root_signal_changes(qtbot, table):
    import qtviz.backends as B

    if "pyqtgraph" not in B.list_available():
        pytest.skip("pyqtgraph backend not registered")

    sel = qv.signal(0)
    builds: list = []

    def build_node():
        builds.append(sel.get())
        return qv.Scatter(table, x="x", y="y")

    view = qv.View(qv.derived(build_node))   # reactive root
    qtbot.addWidget(view)
    assert builds == [0] and view.handle is not None

    sel.set(1)                               # derived re-derives → debounced re-render
    qtbot.waitUntil(lambda: len(builds) >= 2, timeout=2000)
    assert builds[-1] == 1 and view.handle is not None


@pytest.mark.tier2
def test_view_signal_root_rerenders_on_set(qtbot, table):
    import qtviz.backends as B

    if "pyqtgraph" not in B.list_available():
        pytest.skip("pyqtgraph backend not registered")

    s = qv.signal(qv.Scatter(table, x="x", y="y"))
    view = qv.View(s)                        # a plain Signal[Node] root
    qtbot.addWidget(view)
    first = view.handle
    assert first is not None

    s.set(qv.Curve(table, x="x", y="y"))     # debounced re-render
    qtbot.waitUntil(lambda: view.handle is not first, timeout=2000)
    assert view.handle is not None


@pytest.mark.tier2
def test_view_cleans_up_signal_subscription_on_destroy(qtbot, table):
    import qtviz.backends as B

    if "pyqtgraph" not in B.list_available():
        pytest.skip("pyqtgraph backend not registered")

    s = qv.signal(qv.Scatter(table, x="x", y="y"))
    view = qv.View(s)
    qtbot.addWidget(view)
    assert len(s._subs) == 1                 # the View subscribed
    view.deleteLater()
    qtbot.waitUntil(lambda: len(s._subs) == 0, timeout=2000)  # destroyed → unsubscribed


# ── integration: threading (D40) ─────────────────────────────────────────────
@pytest.mark.tier2
def test_set_from_worker_marshals_to_gui(qtbot, qapp):
    from qtviz.threading import Worker

    s = qv.signal(0)
    seen: list = []
    s.subscribe(seen.append)
    worker = Worker()
    try:
        worker.submit(lambda: s.set(42)).result(timeout=2)
        qtbot.waitUntil(lambda: s.get() == 42, timeout=2000)
        assert 42 in seen
    finally:
        worker.stop()
