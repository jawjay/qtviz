"""The legacy Qt WebEngine bridge — PySide6 widgets around a JS visualization
host (Plotly / Bokeh / HoloViews in a ``QWebEngineView``).

Rehomed from the standalone ``qtwebplot`` package (which now re-exports from here
via a deprecation shim). The library-agnostic bridge core lives in
``qtviz.backends.webengine.core``; per-library hosts live in
``qtviz.backends.webengine.ext.*``. The native ``WebEngineBackend`` (Backend
protocol) is built on top of this in W1+ (see ``design/webengine-rehome.md``).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qtviz")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

from qtviz.backends.webengine.backend import PlotBackend
from qtviz.backends.webengine.theme import Theme

__all__ = [
    "Bridge",
    "PlotBackend",
    "PlotView",
    "Theme",
    "WebBridgeView",
    "__version__",
]


def __getattr__(name):
    # Bridge / WebBridgeView / PlotView pull in PySide6 QtWebEngine (Chromium).
    # Importing this package — and registering the `webengine` backend — stays
    # WebEngine-free; the widgets load on first access. Keeps the default test
    # suite Chromium-free and avoids the offscreen-init flake.
    if name == "Bridge":
        from qtviz.backends.webengine.core.bridge import Bridge
        return Bridge
    if name == "WebBridgeView":
        from qtviz.backends.webengine.core.web_bridge_view import WebBridgeView
        return WebBridgeView
    if name == "PlotView":
        from qtviz.backends.webengine.view import PlotView
        return PlotView
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
