"""Tier-1 — the 1.0 API freeze guard ([D82], milestone-1.0-stability).

`qtviz.__all__` is a contract as of 1.0 (`docs/stability.md`). This pins it
EXACTLY: an accidental addition fails the same as an accidental removal.
Changing the surface is allowed — deliberately: update `FROZEN_2_0`, the
CHANGELOG, and (for removals) follow the deprecation path in the same commit.

The [D137] pre-publication amendment (2026-08-05, zero external users, no
first publish yet) revised the frozen set once with the deprecation path
explicitly waived: +Element/Node/QtvizError, −Capabilities/set_backend_priority
(moved to `qtviz.backends`). From first publish onward the waiver is dead.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1

FROZEN_2_0 = frozenset({
    # elements
    "Scatter", "Curve", "Bars", "Image", "Heatmap", "Histogram", "ErrorBars",
    "Spread", "RawFigure",
    "HLine", "VLine", "Span", "Text",            # annotations ([D70])
    "Arrow", "Rect", "Ellipse", "Polygon",        # wave 1 ([D96]/[D97])
    "RefLine",                                    # wave 1 ([D99])
    "BoxPlot", "Violin",                          # statistics ([D67])
    "Area", "Ecdf", "Pie",                        # parity increment 3 ([D84b]/[D90]/[D91])
    "Contour",                                    # parity increment 6 ([D89])
    "Mesh", "Quiver",                             # wave 3 ([D106]/[D107])
    "Stem",                                       # wave 1.4 ([D115])
    "Streamlines",                                # wave 1.5 ([D118])
    # the element base + node union ([D140])
    "Element", "Node",
    # composition + view
    "Overlay", "Layout", "View", "show",  # show: [D134]
    # adapters
    "from_holoviews", "from_holoviews_dmap", "from_hvplot",
    # data binding + raster routing + streaming
    "col", "lit", "tabular", "gridded",
    "set_raster_threshold", "set_raster_size",
    "stream",                        # live sources ([D76])
    # styling
    "Color", "Norm", "Palette", "palettes", "Theme",  # Norm: [D130]
    "set_default_theme",  # [D134]
    "OverlayOptions", "LayoutOptions", "AxisSpec",
    # backend selection ([D140]: Capabilities/set_backend_priority moved to
    # qtviz.backends — the author-facing extension namespace)
    "set_default_backend",
    # the one broad handler ([D140])
    "QtvizError",
    # events
    "Event", "RangeEvent", "PickEvent", "SelectEvent", "HoverEvent", "TapEvent",
    # reactive
    "Signal", "signal", "derived", "effect", "batch",
    # subsystem namespaces + metadata
    "data", "backends", "errors", "threading", "__version__",
})


def test_public_surface_is_frozen():
    current = set(qv.__all__)
    added = sorted(current - FROZEN_2_0)
    removed = sorted(FROZEN_2_0 - current)
    assert not added and not removed, (
        f"public API drifted from the 1.0 freeze ([D82]): added={added}, "
        f"removed={removed} — if deliberate, update FROZEN_2_0 + CHANGELOG "
        f"(removals must follow docs/stability.md's deprecation path)"
    )


def test_every_public_name_resolves():
    for name in FROZEN_2_0 - {"__version__"}:
        assert getattr(qv, name, None) is not None, f"{name} in __all__ but unimportable"


def test_qtwebplot_shim_is_gone():
    """[D79]: the rename shim (promised for two releases, kept for five) is out."""
    with pytest.raises(ModuleNotFoundError):
        import qtwebplot  # noqa: F401


def test_options_is_removed():
    """[D79]: 0.2 promised Options 'importable through 1.0'; the 1.1 cycle
    removes it (docs/stability.md kept to the letter)."""
    assert not hasattr(qv, "Options")
    assert "Options" not in qv.__all__
