"""qtviz — Qt-native declarative plotting (see design/spec.md).

Public API is assembled here as each subsystem lands. This is the import the
acceptance suite (tests/qtviz) targets.
"""

from __future__ import annotations

from . import backends, data, errors, threading  # data layer first, then backends auto-register
from .backends import set_backend_priority, set_default_backend
from .core.capabilities import Capabilities
from .core.color import Color, ColorSpec
from .core.compose import Layout, Overlay, auto_negotiate, negotiate
from .core.event import (
    Event,
    HoverEvent,
    PickEvent,
    RangeEvent,
    SelectEvent,
    TapEvent,
)
from .core.options import LayoutOptions, Options, OverlayOptions
from .core.palette import Palette, palettes
from .core.theme import Theme
from .core.view import View
from .data import (
    Accessor,
    Expression,
    col,
    gridded,
    lit,
    set_raster_size,
    set_raster_threshold,
    tabular,
)
from .elements import (
    Bars,
    Curve,
    ErrorBars,
    Heatmap,
    Histogram,
    Image,
    RawFigure,
    Scatter,
    Spread,
)

__all__ = [
    # elements
    "Scatter", "Curve", "Bars", "Image", "Heatmap", "Histogram", "ErrorBars", "Spread",
    "RawFigure",
    # composition + view
    "Overlay", "Layout", "negotiate", "auto_negotiate", "View",
    # data binding (accessors, D14) + shape overrides (D17) + raster routing (Phase 4)
    "Accessor", "Expression", "col", "lit", "tabular", "gridded",
    "set_raster_threshold", "set_raster_size",
    # styling
    "Color", "ColorSpec", "Palette", "palettes", "Theme",
    "Options", "OverlayOptions", "LayoutOptions",
    # backends + capabilities
    "Capabilities", "set_default_backend", "set_backend_priority",
    # events
    "Event", "RangeEvent", "PickEvent", "SelectEvent", "HoverEvent", "TapEvent",
    # subsystems
    "data", "backends", "errors", "threading",
]
