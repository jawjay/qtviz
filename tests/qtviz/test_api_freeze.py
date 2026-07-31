"""Tier-1 — the 1.0 API freeze guard ([D82], milestone-1.0-stability).

`qtviz.__all__` is a contract as of 1.0 (`docs/stability.md`). This pins it
EXACTLY: an accidental addition fails the same as an accidental removal.
Changing the surface is allowed — deliberately: update `FROZEN_1_0`, the
CHANGELOG, and (for removals) follow the deprecation path in the same commit.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1

FROZEN_1_0 = frozenset({
    # elements
    "Scatter", "Curve", "Bars", "Image", "Heatmap", "Histogram", "ErrorBars",
    "Spread", "RawFigure",
    "HLine", "VLine", "Span", "Text",            # annotations ([D70])
    "Arrow", "Rect", "Ellipse", "Polygon",        # wave 1 ([D96]/[D97])
    "BoxPlot", "Violin",                          # statistics ([D67])
    "Area", "Ecdf", "Pie",                        # parity increment 3 ([D84b]/[D90]/[D91])
    "Contour",                                    # parity increment 6 ([D89])
    # composition + view
    "Overlay", "Layout", "negotiate", "auto_negotiate", "View",
    # adapters
    "from_holoviews", "from_holoviews_dmap", "from_hvplot", "DMapBinding",
    # data binding + raster routing + streaming
    "Accessor", "Expression", "col", "lit", "tabular", "gridded",
    "set_raster_threshold", "set_raster_size",
    "stream", "StreamRef",                        # live sources ([D76])
    # styling
    "Color", "ColorSpec", "Palette", "palettes", "Theme",
    "Options",                                    # deprecated; removal: 1.1 ([D79])
    "OverlayOptions", "LayoutOptions", "AxisSpec",
    # backends + capabilities
    "Capabilities", "set_default_backend", "set_backend_priority",
    # events
    "Event", "RangeEvent", "PickEvent", "SelectEvent", "HoverEvent", "TapEvent",
    # reactive
    "Signal", "signal", "derived", "effect", "batch",
    # subsystem namespaces + metadata
    "data", "backends", "errors", "threading", "__version__",
})


def test_public_surface_is_frozen():
    current = set(qv.__all__)
    added = sorted(current - FROZEN_1_0)
    removed = sorted(FROZEN_1_0 - current)
    assert not added and not removed, (
        f"public API drifted from the 1.0 freeze ([D82]): added={added}, "
        f"removed={removed} — if deliberate, update FROZEN_1_0 + CHANGELOG "
        f"(removals must follow docs/stability.md's deprecation path)"
    )


def test_every_public_name_resolves():
    for name in FROZEN_1_0 - {"__version__"}:
        assert getattr(qv, name, None) is not None, f"{name} in __all__ but unimportable"


def test_qtwebplot_shim_is_gone():
    """[D79]: the rename shim (promised for two releases, kept for five) is out."""
    with pytest.raises(ModuleNotFoundError):
        import qtwebplot  # noqa: F401


def test_options_still_warns_through_1_0():
    """[D79]: 0.2 promised Options 'kept importable through 1.0' — it is; 1.1
    removes it."""
    with pytest.warns(DeprecationWarning):
        qv.Options()
