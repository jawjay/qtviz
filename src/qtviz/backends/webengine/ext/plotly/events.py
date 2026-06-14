"""Plotly-specific typed event payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class PlotlyPoint:
    trace_index: int | None
    point_index: int | None
    x: Any = None
    y: Any = None
    z: Any = None
    text: str | None = None
    curve_number: int | None = None


@dataclass(frozen=True)
class PlotlyHoverEvent:
    points: list[PlotlyPoint]
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlotlyClickEvent:
    points: list[PlotlyPoint]
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlotlySelectionEvent:
    points: list[PlotlyPoint]
    range: dict | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlotlyRelayoutEvent:
    update: dict
    raw: dict = field(default_factory=dict)


class PlotlyEvents(QObject):
    """Typed signals fired by `PlotlyBackend` when JS-side plotly_* events arrive."""

    hover = Signal(PlotlyHoverEvent)
    unhover = Signal(PlotlyHoverEvent)
    click = Signal(PlotlyClickEvent)
    selection = Signal(PlotlySelectionEvent)
    relayout = Signal(PlotlyRelayoutEvent)
