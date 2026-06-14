"""W1 webengine — the live render + event-bridge path.

Display-gated: constructing/tearing down a QWebEngineView under offscreen Qt
segfaults at teardown ("WebEnginePage still not deleted"), so these run only on
a real display. Set QTVIZ_WEBENGINE_GUI=1 to force. The headless proof of the
figure builder and event map is in `test_webengine_figure.py`.
"""

from __future__ import annotations

import os

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("PySide6.QtWebEngineWidgets")
pytest.importorskip("plotly")

pytestmark = [
    pytest.mark.tier2,
    pytest.mark.skipif(
        os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        and os.environ.get("QTVIZ_WEBENGINE_GUI") != "1",
        reason="QWebEngine render/teardown unreliable offscreen; QTVIZ_WEBENGINE_GUI=1 forces",
    ),
]

import qtviz.backends as B  # noqa: E402


@pytest.fixture
def web():
    return B.get("webengine")


def test_render_returns_a_webengine_handle(web, table, qtbot):
    from PySide6.QtWidgets import QWidget  # noqa: PLC0415

    handle = web.render(qv.Scatter(table, x="x", y="y"), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert isinstance(handle.widget, QWidget)
    assert handle.backend_name == "webengine"
    handle.dispose()


def test_click_message_emits_pick_event(web, table, qtbot):
    handle = web.render(qv.Scatter(table, x="x", y="y"), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    got: list = []
    handle.event_bus.subscribe(qv.PickEvent, got.append)
    handle.widget.received.emit(
        "plotly.click", {"points": [{"trace_index": 0, "point_index": 5, "x": 1.0, "y": 2.0}]}
    )
    assert len(got) == 1 and got[0].point_index == 5
    handle.dispose()


def test_relayout_message_emits_range_and_updates_state(web, table, qtbot):
    handle = web.render(qv.Scatter(table, x="x", y="y"), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    got: list = []
    handle.event_bus.subscribe(qv.RangeEvent, got.append)
    handle.widget.received.emit(
        "plotly.relayout",
        {"update": {
            "xaxis.range[0]": 0.0, "xaxis.range[1]": 10.0,
            "yaxis.range[0]": -1.0, "yaxis.range[1]": 1.0,
        }},
    )
    assert got and got[0].x == (0.0, 10.0)
    assert handle.capture_state().x_range == (0.0, 10.0)
    handle.dispose()
