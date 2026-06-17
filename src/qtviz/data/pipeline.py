"""The resolve pipeline (D14, milestone-data-core §4; datashader, Phase 4).

`resolve_node` walks a Node tree and, for each Element, either:
- **rasterizes** it (a scale="datashader" / auto-routed huge Scatter becomes an
  `Image` via datashader — backend-agnostic, out-of-core), or
- resolves its channel accessors into a role-keyed eager ref, or
- materializes a lazy gridded ref.

All of this runs off the GUI thread for lazy / rasterized nodes (see `View`),
so a dask aggregation or compute never blocks the UI.

Duck-typed (a node with `channels()` is an Element; one with `children` is a
composite) so this module stays free of a `core` import cycle.
"""

from __future__ import annotations

import importlib.util

from ..errors import ValidationError
from .ref import EagerTabularRef

# Auto-route to datashader above this many points; configurable via
# set_raster_threshold. Lazy sources of unknown size are routed too (they may be
# huge) — pass scale="native" to force raw rendering.
_RASTER_THRESHOLD = 1_000_000
# default raster resolution (px); the dynamic loop (D21) will use the widget size
_RASTER_SIZE = (800, 600)


def set_raster_threshold(n: int) -> None:
    """scale='auto' rasterizes a Scatter once its point count exceeds `n`."""
    n = int(n)
    if n < 1:
        raise ValidationError(f"raster threshold must be a positive count, got {n}")
    global _RASTER_THRESHOLD
    _RASTER_THRESHOLD = n


def set_raster_size(width: int, height: int) -> None:
    """Default datashader canvas resolution for static rasterization."""
    width, height = int(width), int(height)
    if width < 1 or height < 1:
        raise ValidationError(f"raster size must be positive, got {width}x{height}")
    global _RASTER_SIZE
    _RASTER_SIZE = (width, height)


def _datashader_available() -> bool:
    return importlib.util.find_spec("datashader") is not None


def _safe_size(ref):
    try:
        return ref.size()
    except Exception:
        return None


def _needs_rasterize(node) -> bool:
    scale = getattr(node, "scale", None)  # only point elements (Scatter) carry scale
    if scale in (None, "native"):
        return False
    if scale == "datashader":
        return True  # explicit; _rasterize raises a clear error if datashader is absent
    # scale == "auto"
    if not _datashader_available():
        return False  # fall back to native rendering
    size = _safe_size(getattr(node, "data", None))
    return size is None or size > _RASTER_THRESHOLD


def _rasterize(node):
    if not _datashader_available():
        raise RuntimeError(
            "scale='datashader' requires datashader — install: uv sync --extra datashader"
        )
    from ..elements import Image  # noqa: PLC0415
    from ..ext.datashader import rasterize_element  # noqa: PLC0415

    width, height = _RASTER_SIZE
    result = rasterize_element(node, width=width, height=height)
    image = Image(result.rgba, bounds=result.bounds, id=node.id)  # carry source id for events
    # Stash the (lazy) source element so a backend can re-aggregate to the viewport
    # on pan/zoom (4b, D21), and the pre-shade aggregate for hover reverse-lookup
    # ([D46]). Private → excluded from value identity.
    object.__setattr__(image, "_raster_source", node)
    object.__setattr__(image, "_raster_aggregate", result.aggregate)
    return image


def resolve_node(node):
    """Resolve channel accessors / rasterize. Idempotent: already-resolved
    Elements pass through. Safe off the GUI thread — pure data, no Qt."""
    if hasattr(node, "channels"):  # Element
        if getattr(node, "_resolved", False):
            return node
        if _needs_rasterize(node):
            return _rasterize(node)  # Scatter → datashaded Image
        channels = node.channels()
        if not channels:
            # gridded element (e.g. Image): no tabular channels, but a lazy grid
            # (dask/zarr) must still be materialized here, off the GUI thread.
            # `getattr(..., "data", None)` keeps data-less elements (RawFigure)
            # passing through untouched.
            if getattr(getattr(node, "data", None), "is_lazy", False):
                return node._replace_data(node.data.materialize())
            return node
        arrays = node.data.resolve_channels(channels)
        return node._replace_data(EagerTabularRef(arrays, arrays))
    if hasattr(node, "children"):  # Overlay / Layout
        return node.with_(children=tuple(resolve_node(c) for c in node.children))
    return node


def node_is_lazy(node) -> bool:
    """True if any Element needs off-thread work — an out-of-core (lazy) data ref
    or a datashader rasterization."""
    if hasattr(node, "channels"):
        lazy_ref = bool(getattr(getattr(node, "data", None), "is_lazy", False))
        return lazy_ref or _needs_rasterize(node)
    if hasattr(node, "children"):
        return any(node_is_lazy(c) for c in node.children)
    return False
