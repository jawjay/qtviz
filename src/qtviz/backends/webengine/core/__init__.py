"""Library-agnostic core: WebBridgeView and Bridge.

Knows about web pages and messages. Knows nothing about figures, plots, traces
or any visualization library. Anything chart-shaped lives in `qtwebplot` or
`qtwebplot.ext.*`.
"""

from qtviz.backends.webengine.core.bridge import Bridge
from qtviz.backends.webengine.core.web_bridge_view import WebBridgeView

__all__ = ["Bridge", "WebBridgeView"]
