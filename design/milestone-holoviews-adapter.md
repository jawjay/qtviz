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

**3b — reactive + ecosystem hooks.** Scope **decided** (D43 → Path A; D44 → Level 1);
firm spec in §7.
- `DynamicMap` → **Level 1, one-way re-render** ([D44]). `from_holoviews(dm)` returns a
  `Signal[Node]`: one writable `Signal` per kdim feeds a `derived` that resolves
  `dm[values]` and runs the *static* 3a translation on each frame; the View already
  re-renders on a `Signal[Node]` change (debounced, [D38], `core/view.py`
  `_is_reactive`). Bidirectional stream write-back (`RangeXY`/`Selection1D`/… → hv
  `.event(...)`) is **deferred to L2** (follow-up). Stream-only maps (no kdims) →
  **warn-and-static**.
- `hvplot` → **Path A** ([D43]). hvplot's output is a HoloViews object, so a thin
  `qv.from_hvplot(data, kind=..., **kw)` ( == `from_holoviews(data.hvplot(...))`,
  hvplot imported lazily) is the entry; `hvplot` is an optional extra `[hvplot]`. A
  native `.qtviz` accessor (Path B) is a deferred follow-up; a hv plotting backend
  (Path C) is rejected.

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
- **[D43]** `hvplot` integration mechanism — ✅ **decided: Path A** (translate hvplot
  output via `from_holoviews`; thin `from_hvplot` wrapper; optional `[hvplot]` extra).
  B (`.qtviz` accessor) deferred; C (hv plotting backend) rejected. Briefing:
  `phase3b-decisions.md` §1.
- **[D44]** `DynamicMap`/stream scope for 0.1 — ✅ **decided: Level 1** one-way
  (`DynamicMap`→`Signal[Node]`, kdims exposed as `Signal`s; stream-only → warn-and-
  static). L2 bidirectional write-back deferred. Briefing: `phase3b-decisions.md` §2.

---

## 7. Phase 3b — firm spec (decided 2026-06-15)

Stage 3a (static `from_holoviews`) is shipped. 3b adds **DynamicMap one-way
reactivity** ([D44] L1) and the **hvplot entry point** ([D43] Path A). Both ride
machinery that already exists — the static translation (3a) and the reactive
`Signal[Node]` View root (Phase 4, `core/view.py` `_is_reactive`) — so 3b is mostly
*wiring*, not new subsystems. Spec-first, per cadence: write the verification in §7.6
before the code.

### 7.1 Public API surface (additions)

```python
# qtviz/adapter/holoviews.py  — pure, no Qt, holoviews imported lazily ([D45])
def from_holoviews(obj) -> Node | Signal[Node]:
    # static element/container → Node            (3a, unchanged)
    # DynamicMap               → Signal[Node]    (3b — sugar for from_holoviews_dmap(dm).node)

def from_holoviews_dmap(dm) -> DMapBinding:
    # DMapBinding = (node: Signal[Node], kdims: dict[str, Signal])
    # the composable primitive: drive kdims[name].set(v) → node re-resolves

def from_hvplot(data, kind: str, **kwargs) -> Node | Signal[Node]:
    # == from_holoviews(data.hvplot(kind=kind, **kwargs)); hvplot imported lazily
```

```python
# qtviz/adapter/widgets.py  — Qt-coupled, OPTIONAL helper (kept out of the pure module)
def kdim_panel(dm, *, backend="auto", theme=None) -> QWidget:
    # turnkey: a View(from_holoviews_dmap(dm).node) + one control per kdim,
    #          wired control-change → kdims[name].set(...). Thin; the example is canonical.
```

`Node` is the duck-typed return type that `View` accepts; a `Signal[Node]` is also a
valid `View` root today (`_is_reactive` checks `get` + `subscribe`). So **no `View`
change is required** — `View(from_holoviews(dm))` works the moment the adapter returns
a signal.

### 7.2 `DynamicMap` → `Signal[Node]` (the L1 mechanism)

A `DynamicMap` resolves to a concrete element from **kdim values** (public:
`dm[values]`, equivalently `dm.callback.callable(*values)`) and/or **streams**. L1
handles the kdim/param read side; stream write-back is L2 (deferred).

`from_holoviews_dmap(dm)` builds:

1. **one writable `Signal` per kdim**, initialized to a default (`_kdim_default`):
   discrete kdim → `kdim.default` or `kdim.values[0]`; continuous kdim → `kdim.default`
   or midpoint of `kdim.range`. (Confirm exact accessors against pinned hv at impl.)
2. a **`derived`** node signal:
   `derived(lambda: from_holoviews(dm[tuple(s.get() for s in kdim_signals)]))`.
   The `derived` auto-tracks the kdim signals on first `get()`; setting any kdim signal
   recomputes it and notifies subscribers. **Each resolved frame is translated by the
   *static* 3a `from_holoviews`** — zero new translation code; new elements added to 3a
   are inherited here for free.
3. returns `DMapBinding(node=derived, kdims={kdim.name: signal})`.

`from_holoviews(dm)` ≡ `from_holoviews_dmap(dm).node` — convenient when the map has no
kdims, or is driven by the caller's own upstream `Signal`s/params that the callback
closes over. **Sharp edge:** calling the bare `from_holoviews(dm)` on a *kdim-bearing*
map renders the default frame with no handle to drive it (effectively static). The
example and docs steer kdim-driven use to `from_holoviews_dmap` / `kdim_panel`.
*Micro-decision for impl review:* warn in this case, or stay silent (lean: a one-time
`UserWarning`).

Render flow is the existing debounced path: kdim `Signal.set` → `derived` recomputes →
`View._on_root_signal` → `QTimer(0)` coalesces → `_rebuild` (keeps the prior frame
visible until the new one is ready, `core/view.py`). Lazy frames (out-of-core data in
a resolved element) ride the existing async resolver — no new threading.

### 7.3 `from_hvplot` (D43 Path A)

`df.hvplot.scatter("x","y")` *returns* a HoloViews object (Element / Overlay / often a
`DynamicMap`), only rendered to Bokeh on display. So `from_holoviews` already consumes
it. `from_hvplot(data, kind, **kw)` is the thin convenience that (a) lazily
`import hvplot.pandas` / `.xarray` to register the accessor, (b) calls
`data.hvplot(kind=kind, **kw)`, (c) returns `from_holoviews(result)`. A `groupby=` /
widget / `datashade=True` call yields a `DynamicMap` → §7.2 makes it interactive
natively. Docs also show the raw two-step (`from_holoviews(df.hvplot...())`) so users
aren't forced through the wrapper.

### 7.4 Stream-only `DynamicMap` fallback (no kdims, L2 deferred)

A map driven *only* by streams (e.g. a `RangeXY`-recompute, no kdims) can't be widget-
driven at L1. **Warn-and-static:** resolve the current frame (`dm[()]` /
`dm.callback.callable()`), translate it natively, render it, and emit a `UserWarning`
that live stream interactivity needs L2 — and that `backend="webengine"` via
`RawFigure` ([D28]) is the full-fidelity escape hatch. We do *not* silently pretend
it's interactive.

### 7.5 Datashader handoff (unchanged from §5)

A translated frame that's huge rides qtviz's own `scale="auto"` raster routing
(Phase 4). hvplot `datashade=True` returns a `DynamicMap` whose frames we translate
per §7.2; we do **not** import hv's datashade operation. (Re-aggregation on pan/zoom
is qtviz's existing viewport machinery, not hv's.)

### 7.6 Verification (write before implementing)

- **Tier 1 — translation, no Qt (most coverage).**
  - `from_holoviews(dm)` returns an object with `get`/`subscribe`; `.get()` is the
    default-frame `Node`.
  - `from_holoviews_dmap(dm)` exposes one `Signal` per kdim; setting a kdim signal
    makes `node.get()` return the frame for those values (assert Element type +
    channel→accessor mapping, reusing the 3a assertions). Cover discrete (combo) and
    continuous (range) kdims, and a 2-kdim map.
  - `from_hvplot(df, "scatter", x=…, y=…)` → expected `Node` (gated `importorskip
    hvplot`).
  - Stream-only map → `from_holoviews` returns a static `Node` **and** raises the
    documented `UserWarning` (`pytest.warns`).
- **Tier 2 — pytest-qt offscreen.** `View(from_holoviews(dm))` renders; setting a kdim
  `Signal` re-renders (one coalesced rebuild per tick); `kdim_panel(dm)` builds a
  widget whose control change re-renders. Disposal: destroying the View disposes the
  signal subscription (no leak).
- **Tier 3 — adapter conformance.** Extend `tests/qtviz/test_adapter_conformance.py`
  with a `DynamicMap` case → render on pyqtgraph **and** matplotlib → assert widget +
  primitive counts, mirroring the static cases.
- **hv-version drift.** Existing public-accessor smoke test gains `DynamicMap`
  accessors (`dm.kdims`, `dm[values]`, `kdim.values`/`.range`/`.default`); CI runs
  pinned + latest hv.
- **Benchmarks (Tier 4, per cadence — before TDD).** `@pytest.mark.benchmark`:
  (1) kdim-change → re-resolve → translate latency (the L1 hot path), target the
  debounce stays one-rebuild-per-tick and translate cost tracks 3a; (2) hvplot-output
  translation cost vs. equivalent native construction (overhead should be ~hvplot's
  own build time, not ours).
- **Examples** (each <40 LOC, runnable): `examples/NN_from_holoviews_dynamicmap.py`
  (kdim slider re-plots via `kdim_panel`) and `examples/NN_from_hvplot.py` (one-liner →
  native widget).

### 7.7 Packaging & stability

- New optional extra `hvplot = ["hvplot >=0.10"]` in `pyproject.toml`; add to `all`.
  `holoviews` extra already exists.
- **Lazy imports stay mandatory ([D45]):** `holoviews` inside `from_holoviews`,
  `hvplot` inside `from_hvplot`, Qt inside `widgets.kdim_panel`. `import qtviz` must
  not pull in any of them. Keep the test `importorskip`-before-import ordering; re-run
  the offscreen suite 3× and watch Linux/Windows CI teardown (numba/Qt ordering).

### 7.8 Out of scope for 0.1 (track in `capabilities-gaps.md`)

- **L2 bidirectional stream sync** — native brush/zoom → hv `stream.event(...)`
  write-back (`RangeXY`/`BoundsXY`/`Tap`/`Selection1D`), incl. loop-avoidance and
  `Selection1D` index fidelity. Deferred to a follow-up.
- **`.qtviz` DataFrame accessor** (D43 Path B) — deferred follow-up.
- **hv plotting backend** (D43 Path C) — rejected.
- Pixel-faithful `.opts(...)` styling — structural mapping only (§5, unchanged).

### 7.9 Build order (TDD)

1. Tier-1 + Tier-3 tests for `from_holoviews_dmap` / `from_holoviews(dm)` (red).
2. Implement `from_holoviews_dmap` + `from_holoviews` DynamicMap branch (replace the
   current `UnsupportedHoloViewsElement` raise on `DynamicMap`); make green.
3. Stream-only warn-and-static + its test.
4. `from_hvplot` + tests; add `[hvplot]` extra.
5. `widgets.kdim_panel` + Tier-2 test; both examples.
6. Benchmarks; full offscreen suite 3× + CI pinned/latest hv.
