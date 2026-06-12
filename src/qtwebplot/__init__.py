"""qtwebplot — PySide6 widgets around Qt WebEngine for arbitrary JS visualizations.

The top-level package re-exports the convenience layer. The library-agnostic
core lives in `qtwebplot.core`; per-library extensions live in
`qtwebplot.ext.*`.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qtwebplot")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

from qtwebplot.backend import PlotBackend
from qtwebplot.core import Bridge, WebBridgeView
from qtwebplot.layouts import PlotGrid, PlotTabs
from qtwebplot.view import PlotView

__all__ = [
    "Bridge",
    "PlotBackend",
    "PlotGrid",
    "PlotTabs",
    "PlotView",
    "WebBridgeView",
    "__version__",
]
