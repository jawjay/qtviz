"""qtviz adapters — one-way bridges from other plotting libraries (Phase 3).

`from_holoviews` translates a HoloViews tree into native qtviz Nodes; 3b adds
`from_holoviews_dmap` (reactive DynamicMap binding, [D44]) and `from_hvplot`
([D43]). HoloViews / hvplot / the reactive layer are all imported lazily by the
functions, so importing this package is cheap and has no hard dependency on
holoviews ([D45]).
"""

from __future__ import annotations

from .holoviews import DMapBinding, from_holoviews, from_holoviews_dmap, from_hvplot

__all__ = ["DMapBinding", "from_holoviews", "from_holoviews_dmap", "from_hvplot"]
