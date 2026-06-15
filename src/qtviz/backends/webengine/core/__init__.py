"""Library-agnostic core: WebBridgeView and Bridge.

Knows about web pages and messages. Knows nothing about figures, plots, traces
or any visualization library. Anything chart-shaped lives in `qtwebplot` or
`qtwebplot.ext.*`.
"""

from qtviz.backends.webengine.core.bridge import Bridge  # light (QtCore only)

__all__ = ["Bridge", "WebBridgeView"]


def __getattr__(name):
    # WebBridgeView pulls in PySide6 QtWebEngine (Chromium). Keep it lazy so that
    # importing this package (or `_inject`) stays WebEngine-free.
    if name == "WebBridgeView":
        from qtviz.backends.webengine.core.web_bridge_view import WebBridgeView
        return WebBridgeView
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
