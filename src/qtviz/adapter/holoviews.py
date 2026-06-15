"""`from_holoviews` — translate a HoloViews tree into a native qtviz `Node`.

A thin, one-way shim (`milestone-holoviews-adapter.md`, spec §8). It *reads* a
HoloViews object through its public API only — `.dframe()`, `.kdims`/`.vdims`,
`.dimension_values()` + `.bounds.lbrt()` for gridded, plain iteration for
containers — and *builds* qtviz Elements. No HoloViews internals are touched
([D41]), so the adapter does not rot with HoloViews releases.

Leaves with a native equivalent become that Element; the long tail (Sankey,
Chord, BoxWhisker, …) becomes a webengine `RawFigure` ([D28]).

Stage 3b adds `DynamicMap` one-way reactivity ([D44] Level 1) and the `hvplot`
entry ([D43] Path A), both reusing existing machinery: each resolved DynamicMap
frame is translated by the *static* path below, and a `derived` `Signal[Node]`
driven by per-kdim `Signal`s feeds the View's reactive root (`core/view.py`).

`holoviews` is imported lazily inside `from_holoviews` (not at module top) so that
importing this module — and merely *collecting* its tests — never drags in
numba/llvmlite/bokeh, which destabilizes the offscreen-Qt teardown ([D45]).
`hvplot` and the reactive layer are likewise imported lazily, only when used.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from ..core.compose import Layout, Overlay
from ..data import col
from ..elements import Bars, Curve, ErrorBars, Heatmap, Image, RawFigure, Scatter, Spread
from ..errors import AdapterError, UnsupportedHoloViewsElement


def from_holoviews(obj: Any):
    """Translate a HoloViews element/container into a qtviz `Node`.

    Returns a native Element/`Overlay`/`Layout` where qtviz models the type, else
    a `RawFigure` hosted on the webengine backend. A `DynamicMap` with kdims
    returns a `Signal[Node]` (seeded at default kdim values — use
    `from_holoviews_dmap` to drive the kdims); a stream-only `DynamicMap` renders
    its current frame statically with a warning ([D44] L1). Raises
    `UnsupportedHoloViewsElement` only if even the `RawFigure` fallback cannot apply.
    """
    import holoviews as hv  # noqa: PLC0415 — lazy, see module docstring [D45]

    return _convert(obj, hv)


@dataclass(frozen=True)
class DMapBinding:
    """A reactive `DynamicMap` binding ([D44] Level 1): a `Signal[Node]` plus one
    writable `Signal` per kdim. Setting a kdim signal re-resolves `dm[values]` and
    re-translates the frame, which the View re-renders (debounced). The composable
    primitive — the app drives `kdims[name]` however it likes (custom UI, its own
    `Signal`s); `qtviz.adapter.widgets.kdim_panel` is a turnkey alternative."""

    node: Any              # Signal[Node] (a reactive `derived`)
    kdims: dict            # {kdim_name: Signal}


def from_holoviews_dmap(dm: Any) -> DMapBinding:
    """Build a `DMapBinding` from a HoloViews `DynamicMap` (one-way, [D44] L1).

    One writable `Signal` per kdim (seeded by `_kdim_default`) feeds a `derived`
    `Signal[Node]` that resolves `dm[values]` and runs the static translation on
    each frame. No qtviz→hv write-back (that is Level 2, deferred)."""
    from ..reactive import derived, signal  # noqa: PLC0415 — lazy; keep adapter light

    order = [k.name for k in dm.kdims]
    kdim_signals = {k.name: signal(_kdim_default(k)) for k in dm.kdims}

    def resolve():
        key = tuple(kdim_signals[name].get() for name in order)
        return from_holoviews(dm[key])  # key == () for a no-kdim map

    return DMapBinding(node=derived(resolve), kdims=kdim_signals)


def from_hvplot(data: Any, kind: str, **kwargs: Any):
    """Translate an `hvplot` call into a qtviz `Node` ([D43] Path A).

    `data.hvplot(kind=kind, **kwargs)` returns a HoloViews object (Element /
    Overlay / often a `DynamicMap`), which `from_holoviews` already consumes — so
    this is a thin convenience. `hvplot` is an optional extra (`qtviz[hvplot]`),
    imported lazily here."""
    return from_holoviews(_hvplot_call(data, kind, **kwargs))


def _hvplot_call(data: Any, kind: str, **kwargs: Any) -> Any:
    import contextlib  # noqa: PLC0415
    import importlib  # noqa: PLC0415

    # importing a submodule registers the `.hvplot` accessor on its container type
    for mod in ("hvplot.pandas", "hvplot.xarray", "hvplot.dask"):
        with contextlib.suppress(ImportError):
            importlib.import_module(mod)
    accessor = getattr(data, "hvplot", None)
    if accessor is None:
        raise AdapterError(
            "from_hvplot needs the hvplot accessor on the data object; install the "
            "optional extra with `pip install 'qtviz[hvplot]'`."
        )
    return accessor(kind=kind, **kwargs)


def _kdim_default(kdim: Any) -> Any:
    """Seed value for a kdim `Signal`: explicit default → first discrete value →
    midpoint of a continuous range."""
    if kdim.default is not None:
        return kdim.default
    if kdim.values:
        return kdim.values[0]
    lo, hi = kdim.range
    if lo is not None and hi is not None:
        return (lo + hi) / 2
    raise AdapterError(
        f"DynamicMap kdim {kdim.name!r} has no default, discrete values, or numeric "
        "range to seed a control from; drive it explicitly via from_holoviews_dmap."
    )


def _convert_dynamicmap(dm: Any) -> Any:
    if dm.kdims:
        warnings.warn(
            f"from_holoviews on a DynamicMap with kdims {[k.name for k in dm.kdims]!r} "
            "returns a Signal[Node] seeded at default kdim values, with no handle to "
            "drive them. Use from_holoviews_dmap(dm) for the kdim Signals, or "
            "qtviz.adapter.widgets.kdim_panel(dm) for a turnkey control panel.",
            UserWarning,
            stacklevel=3,
        )
        return from_holoviews_dmap(dm).node
    # No kdims → can't be widget-driven at L1. Warn-and-static: render the current
    # frame; live stream interactivity is Level 2 (deferred, [D44]).
    if dm.streams:
        warnings.warn(
            "from_holoviews on a stream-only DynamicMap renders its current frame "
            "statically; live stream interactivity (RangeXY/Selection1D/Tap/...) is "
            "deferred to Level 2. For full fidelity host it on backend='webengine'.",
            UserWarning,
            stacklevel=3,
        )
    return from_holoviews(dm[()])


def _convert(obj: Any, hv) -> Any:
    # ── reactive / lazy first: DynamicMap → Signal[Node] or warn-and-static ────
    if isinstance(obj, hv.DynamicMap):
        return _convert_dynamicmap(obj)

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
