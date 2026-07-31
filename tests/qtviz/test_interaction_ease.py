"""Parity program increment 8 — interaction ease ([D95]).

`View(toolbar=True)` shows the backend's native toolbar where one exists
(matplotlib; pyqtgraph/webengine interaction is already native → no-op), and
matplotlib gains an interactive rubber-band brush that emits the same
`SelectEvent`s as the programmatic `select_bounds`.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": [0.0, 1.0, 2.0, 3.0], "y": [0.0, 1.0, 0.5, 1.5]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier2
def test_view_toolbar_on_matplotlib(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

    view = qv.View(qv.Scatter(_T, x="x", y="y"), backend="matplotlib", toolbar=True)
    qtbot.addWidget(view)
    widgets = [view._layout.itemAt(i).widget() for i in range(view._layout.count())]
    assert any(isinstance(w, NavigationToolbar2QT) for w in widgets)


@pytest.mark.tier2
def test_view_toolbar_default_off(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

    view = qv.View(qv.Scatter(_T, x="x", y="y"), backend="matplotlib")
    qtbot.addWidget(view)
    widgets = [view._layout.itemAt(i).widget() for i in range(view._layout.count())]
    assert not any(isinstance(w, NavigationToolbar2QT) for w in widgets)


@pytest.mark.tier2
def test_view_toolbar_noop_on_pyqtgraph(qtbot):
    if "pyqtgraph" not in qv.backends.list_available():
        pytest.skip("pyqtgraph not registered")
    view = qv.View(qv.Scatter(_T, x="x", y="y"), backend="pyqtgraph", toolbar=True)
    qtbot.addWidget(view)
    assert view._toolbar_widget is None  # native interaction — nothing to add


@pytest.mark.tier2
def test_mpl_interactive_brush_wired_and_emits(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.widgets import RectangleSelector

    handle = _backend("matplotlib").render(qv.Scatter(_T, x="x", y="y"),
                                           theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert isinstance(ax._qtviz_brush, RectangleSelector)
    got = []
    handle.event_bus.subscribe(qv.SelectEvent, got.append)
    # the selector's release path funnels into the same shared helper:
    from qtviz.backends.matplotlib import _events

    _events.emit_bounds_select(handle._surfaces[0]["selectables"],
                               handle.event_bus, 0.5, -1.0, 2.5, 2.0)
    handle.event_bus._drain()
    assert len(got) == 1
    assert np.array_equal(got[0].indices, [1, 2])
    assert got[0].bounds == (0.5, -1.0, 2.5, 2.0)
