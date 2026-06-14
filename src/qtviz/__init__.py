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
from .data import Accessor, Expression, col, lit
from .elements import (
    Bars,
    Curve,
    ErrorBars,
    Heatmap,
    Histogram,
    Image,
    Scatter,
    Spread,
)

__all__ = [
    # elements
    "Scatter", "Curve", "Bars", "Image", "Heatmap", "Histogram", "ErrorBars", "Spread",
    # composition + view
    "Overlay", "Layout", "negotiate", "auto_negotiate", "View",
    # data binding (accessors, D14)
    "Accessor", "Expression", "col", "lit",
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
