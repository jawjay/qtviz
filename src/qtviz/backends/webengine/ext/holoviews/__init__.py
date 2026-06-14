"""HoloViews extension for qtwebplot.

Requires the `holoviews` optional dependency (install `qtwebplot[holoviews]`).
By default renders via Bokeh, reusing the `qtwebplot.ext.bokeh.BokehBackend`
event wiring and verb surface.
"""

from qtviz.backends.webengine.ext.holoviews.backend import HoloViewsBackend

__all__ = ["HoloViewsBackend"]
