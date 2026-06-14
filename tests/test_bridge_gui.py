"""GUI smoke test for the core bridge — round-trips a message through
WebBridgeView with a plain HTML fixture (no plotting library involved).

Skipped automatically if pytest-qt or PySide6's WebEngine aren't importable.
Run with:  QT_QPA_PLATFORM=offscreen pytest tests/test_bridge_gui.py -v
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6.QtWebEngineWidgets")

# The QWebEngine `ready` handshake is unreliable under the offscreen Qt platform
# (no GPU/compositor), so these GUI tests time out in headless CI/local. Skip
# there; set QTVIZ_WEBENGINE_GUI=1 to force them on a host where it works.
pytestmark = pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    and os.environ.get("QTVIZ_WEBENGINE_GUI") != "1",
    reason="QWebEngine ready handshake unreliable offscreen; set QTVIZ_WEBENGINE_GUI=1 to force",
)

from qtwebplot import WebBridgeView  # noqa: E402

FIXTURE_HTML = """
<!doctype html>
<html><head><title>t</title></head>
<body>
  <p id="p">hi</p>
  <script>
    qtwebplot.onReady(function () {
      qtwebplot.on("ping", function (p) {
        qtwebplot.send("pong", {echo: p});
      });
      qtwebplot.send("hello", {from: "js"});
    });
  </script>
</body></html>
"""


@pytest.mark.gui
def test_ready_and_roundtrip(qtbot):
    view = WebBridgeView()
    qtbot.addWidget(view)
    view.resize(400, 200)

    messages: list[tuple[str, object]] = []
    view.received.connect(lambda name, payload: messages.append((name, payload)))

    with qtbot.waitSignal(view.ready, timeout=10_000):
        view.load_html(FIXTURE_HTML)

    # JS should have already emitted "hello" by ready time.
    def has_hello() -> bool:
        return any(name == "hello" for name, _ in messages)

    qtbot.waitUntil(has_hello, timeout=5_000)

    # Now round-trip: Py -> JS via send, JS responds via send.
    view.send("ping", {"x": 1})

    def has_pong() -> bool:
        return any(name == "pong" for name, _ in messages)

    qtbot.waitUntil(has_pong, timeout=5_000)

    pong = next(p for n, p in messages if n == "pong")
    assert isinstance(pong, dict)
    assert pong.get("echo", {}).get("x") == 1
