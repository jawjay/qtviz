"""Plotly extension for qtwebplot.

Requires the `plotly` optional dependency (install `qtwebplot[plotly]`).
"""

from qtviz.backends.webengine.ext.plotly.backend import PlotlyBackend
from qtviz.backends.webengine.ext.plotly.events import (
    PlotlyClickEvent,
    PlotlyEvents,
    PlotlyHoverEvent,
    PlotlyRelayoutEvent,
    PlotlySelectionEvent,
)

__all__ = [
    "PlotlyBackend",
    "PlotlyClickEvent",
    "PlotlyEvents",
    "PlotlyHoverEvent",
    "PlotlyRelayoutEvent",
    "PlotlySelectionEvent",
]
