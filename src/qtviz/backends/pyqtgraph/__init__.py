"""pyqtgraph backend — the primary, native, hard-dependency backend (spec §4.1)."""

from __future__ import annotations

from .render import PyQtGraphBackend

backend = PyQtGraphBackend()

__all__ = ["backend", "PyQtGraphBackend"]
