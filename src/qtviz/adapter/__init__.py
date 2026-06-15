"""qtviz adapters — one-way bridges from other plotting libraries (Phase 3).

`from_holoviews` translates a HoloViews tree into native qtviz Nodes. HoloViews
itself is imported lazily by the function, so importing this package is cheap and
has no hard dependency on holoviews ([D45]).
"""

from __future__ import annotations

from .holoviews import from_holoviews

__all__ = ["from_holoviews"]
