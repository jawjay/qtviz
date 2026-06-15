# Milestone — Phase 3: HoloViews adapter (`from_holoviews`)

> A thin, **one-way** shim: translate a HoloViews object tree into a native qtviz
> `Node`, render it through pyqtgraph/matplotlib, and fall back to `RawFigure`
> on webengine for elements qtviz doesn't model. HoloViews-fluent users get a
> Qt-native widget in one call; coverage grows as qtviz grows, not as we PR
> upstream. Spec-first plan (per workflow cadence) — **not yet implemented**.
> Gate cleared by **[D41]** (Spike-P2: 10/10 render via public API, no internals).
> Companions: `native-pivot-research.md` §2e–2f (why one-way adapter), spec §8,
> `milestone-color-encoding.md` ([D23], a prerequisite). References `discussion-items.md` as **[D#]**.

## 1. The shape

```
qtviz.from_holoviews(hv_obj) -> Node            # pure: hv tree → qtviz tree
        │  walk (public API only: .dframe / .kdims / .vdims / iteration)
        ▼
   Overlay / Layout (containers)  ·  Scatter / Curve / … (leaves)  ·  RawFigure (fallback)
        │  View(node, backend=…)  — the normal render path, unchanged
        ▼
   QWidget  (pyqtgraph | matplotlib native; webengine for fallbacks)
```

Three decisions keep this a clean, low-maintenance foundation:

1. **One-way and pure.** `from_holoviews(obj) -> Node` is a pure function with no
   Qt and no hv-rendering — it only *reads* the hv object and *builds* qtviz
   Elements. It returns a `Node`, so it composes with everything (`View`,
   `Overlay`/`Layout`, reactive `Signal`) for free and is Tier-1 testable without a
   display. We never translate qtviz → hv.
2. **Public API only — proven, not assumed.** [D41] established that every leaf
   reads through `.dframe()`, `.kdims`/`.vdims` (`.name`), `.dimension_values(2,
   flat=False)` + `.bounds.lbrt()` (gridded), and containers through plain
   iteration. **No private surface** → the adapter does not rot with hv releases
   (roadmap §6 #3 risk retired). CI pins a tested hv range and also runs latest to
   catch drift early.
3. **Translate what we model; fall back for the rest.** Leaves with a native qtviz
   equivalent become that Element; the long tail (Sankey, Chord, Graph, …) becomes
   `RawFigure(hv.renderer("bokeh").get_plot(obj).state)` hosted on webengine
   ([D26], [D28]). The adapter ships incrementally: common elements native and
   fast, everything else still renders full-fidelity.

## 2. Translation table

Dimensions map **by role per element type**, not by blind position — hv
auto-promotes undeclared DataFrame columns to vdims, so position is unsafe ([D41]).

| HoloViews | qtviz | Mapping |
|-----------|-------|---------|
| `Scatter` | `Scatter` | x=`kdims[0]`, y=`vdims[0]`, `.dframe()` |
| `Points` | `Scatter` | x=`kdims[0]`, y=`kdims[1]` (both kdims) |
| `Curve` | `Curve` | x=`kdims[0]`, y=`vdims[0]` |
| `Bars` | `Bars` | x=`kdims[0]` (categorical ok), y=`vdims[0]` |
| `HeatMap` | `Heatmap` | x=`kdims[0]`, y=`kdims[1]`, z=`vdims[0]`, tidy `.dframe()` |
| `Image`/`Raster` | `Image` | `dimension_values(2, flat=False)` + `bounds.lbrt()` |
| `ErrorBars` | `ErrorBars` | x=`kdims[0]`, y=`vdims[0]`; symmetric `[y, err]`→`err=col(err)`; asymmetric `[y, neg, pos]`→`err=(col(neg), col(pos))` |
| `Spread` | `Spread` | x=`kdims[0]`, vdims `[y, Δ]` → `y_lo=col(y)-col(Δ)`, `y_hi=col(y)+col(Δ)` (Expression arithmetic) |
| `Histogram` | `Bars` | pre-binned (kdim=bin center, vdim=Frequency) → `Bars(x=center, y=freq)`; qtviz `Histogram` bins a *raw* column, so it is the wrong target |
| `Area` | `Spread` or `Curve` | band (`[y, y2]`)→`Spread`; single vdim→`Curve` (filled-curve styling deferred) |
| `Overlay`, `NdOverlay` | `Overlay` | `tuple(from_holoviews(c) for c in obj)` |
| `Layout`, `NdLayout` | `Layout(kind="grid")` | iterate children; nesting works |
| `GridSpace` | `Layout(kind="grid")` | 2-D arrangement → grid panes |
| `DynamicMap` | `Signal[Node]` | §4 — re-render on hv stream events |
| *unmodeled* | `RawFigure` (webengine) | `hv.renderer("bokeh").get_plot(obj).state` ([D28]) |

Unsupported-with-no-fallback (shouldn't happen once RawFigure lands) raises
`UnsupportedHoloViewsElement(type(obj).__name__)` with the "use `hv.render` / webengine" hint.

## 3. Build stages

**3a — static adapter (the bulk; Tier-1 + conformance).**
- New package `src/qtviz/adapter/` with `holoviews.py::from_holoviews`; export
  `qtviz.from_holoviews`. Dispatch on public hv classes (containers first, then
  leaves), role-based dim mapping per the table. Pure, no Qt.
- `errors.UnsupportedHoloViewsElement`.
- Covers all rows above except `DynamicMap`/streams and `hvplot`.

**3b — reactive + ecosystem hooks.**
- `DynamicMap` → subscribe to hv's stream/param events; each update recomputes the
  node and pushes it into a `Signal[Node]`, driving the existing debounced
  View-root rebuild ([D38]). Bidirectional stream sync (`RangeXY`/`BoundsXY`/`Tap`/
  `Selection1D`): qtviz typed Events forward to the hv stream's `.event(...)` so
  HoloViews-side callbacks fire normally (spec §8). **Scope for 0.1 is an open
  decision — see [D44].**
- `hvplot` extension so `df.hvplot(kind="scatter", backend="qtviz")` (or a `.qtviz`
  accessor) returns a native widget — **mechanism is an open decision, [D43].**

**Fallback wiring (spans 3a/3b).** Detect "no native mapping" and emit `RawFigure`
on webengine. Reuses the existing `RawFigure`/`HoloViewsBackend` host ([D26],
[D31]); the adapter only needs the hv→bokeh `.state` handoff and to route the node
to `backend="webengine"`.

## 4. Verification (spec-first, write before implementing)

- **Tier 1 — translation (no Qt).** `from_holoviews(obj)` builds the expected
  `Node` tree: right Element type, right channel→accessor mapping, container
  nesting preserved. Cover every table row incl. the role-mapping traps (Points
  two-kdim, Scatter+extra-column, ErrorBars symmetric/asymmetric, Spread Δ→lo/hi,
  Histogram→Bars). This is where most coverage lives — fast, display-free.
- **Tier 3 — adapter conformance.** A round-trip suite (parallel to
  `tests/qtviz/test_adapter_conformance.py`): each hv element → `from_holoviews` →
  render on pyqtgraph **and** matplotlib → assert a widget + key primitive counts,
  mirroring `test_backend_conformance.py`. Reuse the Spike-P2 case set as the seed.
- **hv-version drift.** CI runs the pinned hv and latest; a smoke test asserts the
  public accessors the adapter depends on still exist (fail loud, early).
- **Examples** (each <40 LOC, runnable, in `examples/`): `from_holoviews(scatter *
  curve)`, an hv `Layout`, a `DynamicMap` widget, and an `hvplot` one-liner.
- New deps as an optional extra `[holoviews]` (holoviews already present in dev).
- **Suite-stability constraint ([D45]).** Importing `holoviews` (it drags in
  numba/llvmlite + bokeh) at *collection* time crashes the offscreen-Qt suite at
  interpreter teardown — the spec-first modules dodge it by ordering the
  adapter-absent `importorskip` **before** the holoviews import. Once the adapter
  lands and the tests activate, the import returns: mitigate by importing
  holoviews **lazily inside `from_holoviews`** (not at `qtviz.adapter.holoviews`
  module top) so merely importing the adapter is cheap and safe, and re-check
  full-run teardown then.

## 5. Deliberate limits (track in `capabilities-gaps.md`)

- **One-way only** — no qtviz → hv.
- **Styling is structural, not pixel-faithful.** We map data + channels + theme,
  not every hv `.opts(...)`. Filled-`Area`, per-`Curve`/`Bars` color encoding, and
  legends-as-elements follow `milestone-color-encoding.md` §3's open items.
- **`DynamicMap`/stream depth** bounded by [D44].
- **Datashader handoff** — a huge translated `Scatter` rides the existing
  `scale="auto"` raster routing; we do *not* import hv's own datashade operation.

## 6. Discussion items

- **[D28]** `from_holoviews` fallback to webengine `RawFigure` — ✅ principle
  accepted; wired here.
- **[D41]** Spike-P2 feasibility — ✅ GO; role-based mapping + the Histogram/Spread
  shape decisions above come from it.
- **[D42]** `Histogram`/`Spread` shape handling — **recommend** map hv `Histogram`→
  `Bars` (it's pre-binned) and hv `Spread`→`Spread` via Expression `y±Δ`; no qtviz
  API change. *Open — confirm at boundary.*
- **[D43]** `hvplot` integration mechanism — register a `qtviz` hvplot backend vs.
  ship a thin `.qtviz` DataFrame accessor. *Open — recommend deciding when 3b starts.*
- **[D44]** `DynamicMap`/stream scope for 0.1 — one-way (kdim-widget → re-render)
  vs. full bidirectional stream sync. **Recommend** one-way re-render for 0.1, defer
  bidirectional `Selection1D`/`RangeXY` write-back. *Open.*
