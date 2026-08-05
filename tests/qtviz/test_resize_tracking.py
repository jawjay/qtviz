"""The rendered plot respects the outer widget's size (owner ask, 2026-08-04).

Native backends: the handle widget must track the View through Qt layouts —
growing AND shrinking (a canvas that enforces a large minimum breaks embedding).
Webengine: the Qt side must track the same way; the in-page half rides Plotly's
`responsive: true` config plus the `resized` → `plotly.resize` bridge nudge
(exercised at the unit level here; offscreen QWebEngine can't paint).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": np.arange(50.0), "y": np.arange(50.0) ** 0.5}


def _settle(qtbot, view):
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_native_plot_tracks_grow_and_shrink(qtbot, backend):
    if backend not in qv.backends.list_available():
        pytest.skip(f"{backend} not registered")
    view = qv.View(qv.Scatter(_T, x="x", y="y").opts(title="t"), backend=backend)
    qtbot.addWidget(view)
    view.resize(640, 480)
    view.show()
    _settle(qtbot, view)
    inner = view.handle.widget

    view.resize(900, 700)
    qtbot.waitUntil(lambda: inner.width() > 880, timeout=2000)
    assert inner.height() > 680

    view.resize(240, 180)  # shrink hard — no oversized minimums
    qtbot.waitUntil(lambda: inner.width() < 260, timeout=2000)
    assert inner.height() < 200


@pytest.mark.tier2
def test_matplotlib_figure_rerenders_at_the_new_size(qtbot):
    if "matplotlib" not in qv.backends.list_available():
        pytest.skip("matplotlib not registered")
    view = qv.View(qv.Curve(_T, x="x", y="y"), backend="matplotlib")
    qtbot.addWidget(view)
    view.resize(640, 480)
    view.show()
    _settle(qtbot, view)
    canvas = view.handle.widget
    view.resize(900, 700)
    qtbot.waitUntil(lambda: canvas.get_width_height()[0] > 850, timeout=2000)


@pytest.mark.tier2
def test_layout_panes_share_the_outer_size(qtbot):
    view = qv.View(qv.Curve(_T, x="x", y="y") + qv.Histogram(_T, value="y"),
                   backend="pyqtgraph")
    qtbot.addWidget(view)
    view.resize(800, 400)
    view.show()
    _settle(qtbot, view)
    view.resize(400, 200)
    qtbot.waitUntil(lambda: view.handle.widget.width() < 420, timeout=2000)


@pytest.mark.tier2
def test_webbridgeview_emits_resized_and_plotly_backend_nudges(qtbot):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    from qtviz.backends.webengine.core.web_bridge_view import WebBridgeView
    from qtviz.backends.webengine.ext.plotly.backend import PlotlyBackend

    view = WebBridgeView()
    qtbot.addWidget(view)
    fired = []
    view.resized.connect(lambda: fired.append(True))
    view.resize(300, 200)
    view.show()
    view.resize(500, 400)
    assert fired  # the Qt half reports resizes

    backend = PlotlyBackend({"data": [], "layout": {}})
    sent = []
    backend._view = type("V", (), {"send": lambda self, n, p: sent.append(n)})()
    backend.resize()
    assert sent == ["plotly.resize"]  # the bridge verb reaches JS


@pytest.mark.tier2
def test_plotly_backend_nudges_after_a_qt_resize(qtbot):
    """End-to-end wiring: Qt resize → debounce → the queued bridge command
    (pre-handshake sends queue on the bridge — exactly the gap the nudge
    closes for resizes that land while the page is still loading)."""
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    pytest.importorskip("plotly")
    from qtviz.backends.webengine.ext.plotly.backend import PlotlyBackend
    from qtviz.backends.webengine.view import PlotView

    view = PlotView(PlotlyBackend({"data": [], "layout": {}}))
    qtbot.addWidget(view)
    # Observe the send itself, not the pre-ready queue: whether the command
    # lands in `_command_queue` or goes straight over the bridge depends on
    # when Chromium's handshake completes — a race that flaked on CI both
    # ways. The wiring under test is resize → debounce → send(...).
    sent: list[str] = []
    orig_send = view.send

    def send(name, payload=None):
        sent.append(name)
        orig_send(name, payload)

    view.send = send
    view.resize(300, 200)
    view.show()
    qtbot.wait(50)  # let Chromium construction/show settle before the resize
    view.resize(500, 400)
    # generous: a cold CI runner spends seconds spinning up QtWebEngine on the
    # GUI thread before the debounce timer can even be processed.
    qtbot.waitUntil(lambda: "plotly.resize" in sent, timeout=10000)
