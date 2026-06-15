"""`from_holoviews` — translate a HoloViews tree into a native qtviz `Node`.

A thin, one-way shim (`milestone-holoviews-adapter.md`, spec §8). It *reads* a
HoloViews object through its public API only — `.dframe()`, `.kdims`/`.vdims`,
`.dimension_values()` + `.bounds.lbrt()` for gridded, plain iteration for
containers — and *builds* qtviz Elements. No HoloViews internals are touched
([D41]), so the adapter does not rot with HoloViews releases.

Leaves with a native equivalent become that Element; the long tail (Sankey,
Chord, BoxWhisker, …) becomes a webengine `RawFigure` ([D28]). `DynamicMap` /
streams / `hvplot` are stage 3b.

`holoviews` is imported lazily inside `from_holoviews` (not at module top) so that
importing this module — and merely *collecting* its tests — never drags in
numba/llvmlite/bokeh, which destabilizes the offscreen-Qt teardown ([D45]).
"""

from __future__ import annotations

from typing import Any

from ..core.compose import Layout, Overlay
from ..data import col
from ..elements import Bars, Curve, ErrorBars, Heatmap, Image, RawFigure, Scatter, Spread
from ..errors import UnsupportedHoloViewsElement


def from_holoviews(obj: Any):
    """Translate a HoloViews element/container into a qtviz `Node`.

    Returns a native Element/`Overlay`/`Layout` where qtviz models the type, else
    a `RawFigure` hosted on the webengine backend. Raises
    `UnsupportedHoloViewsElement` only if even that fallback cannot apply.
    """
    import holoviews as hv  # noqa: PLC0415 — lazy, see module docstring [D45]

    return _convert(obj, hv)


def _convert(obj: Any, hv) -> Any:
    # ── containers (iterate to child elements; `list(obj)` yields values for
    #    Overlay / Layout / NdOverlay / NdLayout / GridSpace) ──────────────────
    if isinstance(obj, (hv.Overlay, hv.NdOverlay)):
        return Overlay(tuple(_convert(c, hv) for c in obj))
    if isinstance(obj, (hv.Layout, hv.NdLayout, hv.GridSpace)):
        return Layout(tuple(_convert(c, hv) for c in obj), kind="grid")

    # ── leaves — most-specific class first: Area ⊂ Curve, Spread ⊂ ErrorBars ──
    if isinstance(obj, hv.Points):  # both axes are kdims (no vdim)
        return Scatter(obj.dframe(), x=obj.kdims[0].name, y=obj.kdims[1].name)
    if isinstance(obj, hv.Scatter):
        return Scatter(obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.Area):  # band [y, y2] → Spread; single vdim → Curve
        if len(obj.vdims) >= 2:
            return Spread(obj.dframe(), x=obj.kdims[0].name,
                          y_lo=col(obj.vdims[0].name), y_hi=col(obj.vdims[1].name))
        return Curve(obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.Curve):
        return Curve(obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.Histogram):  # pre-binned (center, Frequency) → Bars [D42]
        return Bars(obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.Bars):
        return Bars(obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.HeatMap):
        return Heatmap(obj.dframe(), x=obj.kdims[0].name, y=obj.kdims[1].name,
                       z=obj.vdims[0].name)
    if isinstance(obj, hv.Spread):  # vdims [y, Δ] → y ± Δ [D42]
        y, delta = obj.vdims[0].name, obj.vdims[1].name
        return Spread(obj.dframe(), x=obj.kdims[0].name,
                      y_lo=col(y) - col(delta), y_hi=col(y) + col(delta))
    if isinstance(obj, hv.ErrorBars):
        x, y = obj.kdims[0].name, obj.vdims[0].name
        if len(obj.vdims) >= 3:  # [y, neg, pos] → asymmetric (lo, hi)
            err = (col(obj.vdims[1].name), col(obj.vdims[2].name))
        else:  # [y, err] → symmetric
            err = col(obj.vdims[1].name)
        return ErrorBars(obj.dframe(), x=x, y=y, err=err)
    if isinstance(obj, hv.Image):  # gridded value array + bounds
        arr = obj.dimension_values(2, flat=False)
        return Image(arr, bounds=tuple(float(b) for b in obj.bounds.lbrt()))

    # ── fallback: host the whole figure on webengine, unchanged ([D28]) ───────
    if isinstance(obj, hv.core.Element):
        return RawFigure(obj, kind="holoviews")

    raise UnsupportedHoloViewsElement(
        f"from_holoviews cannot translate {type(obj).__name__!r}; "
        "render it with hv.render(...) or host it on the webengine backend."
    )
