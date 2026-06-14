"""Bokeh-specific typed event payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class BokehTapEvent:
    x: float | None
    y: float | None
    sx: float | None = None
    sy: float | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BokehDoubleTapEvent:
    x: float | None
    y: float | None
    sx: float | None = None
    sy: float | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BokehSelectionEvent:
    geometry: dict | None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BokehRangesUpdateEvent:
    x0: float | None
    x1: float | None
    y0: float | None
    y1: float | None
    raw: dict = field(default_factory=dict)


class BokehEvents(QObject):
    """Typed signals fired by `BokehBackend` when JS-side Bokeh events arrive."""

    tap = Signal(BokehTapEvent)
    double_tap = Signal(BokehDoubleTapEvent)
    selection = Signal(BokehSelectionEvent)
    ranges_update = Signal(BokehRangesUpdateEvent)
