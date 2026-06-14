"""Tier-2 — View lifecycle, events, threading (spec §2.9, §2.10, §2.14).

These need a Qt event loop (pytest-qt's `qtbot`/`qapp`); the View tests also
need at least one registered backend and skip until one exists. The threading
tests stand alone — they exercise the GUI-thread discipline directly.
"""

from __future__ import annotations

import threading

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier2


@pytest.fixture
def any_backend():
    import qtviz.backends as B

    names = [getattr(n, "name", n) for n in B.list_available()]
    if not names:
        pytest.skip("no backend registered yet")
    return names[0]


# ── View lifecycle (needs a backend) ─────────────────────────────────────────
def test_view_builds_a_widget(table, any_backend, qtbot):
    view = qv.View(qv.Scatter(table, x="x", y="y"), backend=any_backend)
    qtbot.addWidget(view)
    assert view.handle.backend_name == any_backend


def test_set_theme_and_set_root(table, any_backend, qtbot):
    view = qv.View(qv.Scatter(table, x="x", y="y"), backend=any_backend)
    qtbot.addWidget(view)
    view.set_theme(qv.Theme.dark())     # no raise
    view.set_root(qv.Curve(table, x="x", y="y"))
    assert view.handle is not None


def test_on_returns_disposable(table, any_backend, qtbot):
    view = qv.View(qv.Scatter(table, x="x", y="y"), backend=any_backend)
    qtbot.addWidget(view)
    disposable = view.on(qv.RangeEvent, lambda ev: None)
    disposable.dispose()  # no raise


def test_auto_backend_resolves_homogeneous_grid(table, any_backend, qtbot):
    # regression: a Layout(grid) under backend="auto" must resolve to one
    # concrete backend, not the per-pane "auto" sentinel.
    layout = qv.Layout([qv.Scatter(table, x="x", y="y"), qv.Curve(table, x="x", y="y")])
    view = qv.View(layout, backend="auto")
    qtbot.addWidget(view)
    assert view.handle is not None


def test_subscription_survives_backend_switch(table, qtbot):
    import qtviz.backends as B

    names = [getattr(n, "name", n) for n in B.list_available()]
    if len(names) < 2:
        pytest.skip("need two backends to test a switch")
    view = qv.View(qv.Scatter(table, x="x", y="y"), backend=names[0])
    qtbot.addWidget(view)
    disposable = view.on(qv.RangeEvent, lambda ev: None)
    view.set_backend(names[1])
    assert view.handle.backend_name == names[1]
    disposable.dispose()  # the pre-switch Disposable is still valid (Q-K)


# ── threading discipline (needs only a QApplication) ─────────────────────────
def test_require_gui_thread_allows_main_blocks_worker(qapp):
    qthreading = pytest.importorskip("qtviz.threading")

    @qthreading.require_gui_thread
    def guarded():
        return "ok"

    assert guarded() == "ok"  # on the GUI thread

    err: list[BaseException] = []

    def off_thread():
        try:
            guarded()
        except BaseException as e:  # noqa: BLE001
            err.append(e)

    t = threading.Thread(target=off_thread)
    t.start()
    t.join()
    assert err and isinstance(err[0], RuntimeError)


def test_run_on_gui_short_circuits_on_gui_thread(qapp):
    qthreading = pytest.importorskip("qtviz.threading")
    assert qthreading.is_gui_thread() is True
    result = qthreading.run_on_gui(lambda: 42, block=True)
    value = result.result() if hasattr(result, "result") else result
    assert value == 42  # no deadlock when already on the GUI thread (Q-E)
