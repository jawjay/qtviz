"""matplotlib backend — optional extra, publication-quality + vector export."""

from __future__ import annotations

from .render import MatplotlibBackend

backend = MatplotlibBackend()

__all__ = ["backend", "MatplotlibBackend"]
