# Milestone — 0.2 "Hardening + escape valve" (R4 + R1)

> The first milestone driven by `weakness-root-causes.md`. It closes the two root
> causes that are **cheap and high-trust** to address now: **R4** (declared-but-
> unenforced contracts → silent parameter drops) and **R1**'s practical pain (the
> abstraction has no escape valve to backend-native power), via a purity-preserving
> accessor. It is deliberately *not* about new chart features — it makes the existing
> surface **honest** and gives developers a way out when they hit the
> lowest-common-denominator ceiling.
>
> Decisions: **[D51]** (contract enforcement = honor-or-warn), **[D52]** (capability
> honesty), **[D53]** (`handle.native` escape valve). Companions: `weakness-root-
> causes.md` §2 (R1, R4), §6 (DP1, DP3); `spec.md` §3.4 / §2.5 / §2.8.

## 0. Goal & non-goals

**Goal.** A developer can trust that *every option qtviz accepts either does something
or says it doesn't*, that *every declared capability is real*, and that *when the
8-element / 5-event ceiling isn't enough, there is a documented, supported way to reach
the live backend object.*

**In scope.** DP1 (the §3.4 honor-or-warn mechanism, made real + guarded by a
conformance test; wire the trivial honors; capability honesty; deprecate dead surface)
and DP3 (`RenderHandle.native(element_id)` / `View.native(element_id)`).

**Out of scope (later milestones / non-goals).** Implementing the *unbuilt* features
behind the warned options — real `Heatmap.aggregator` reduction and grouped/stacked
`Bars` are **0.4 vocabulary growth**, not here; they only need to **warn-and-degrade**
honestly now. First-class axes (0.3 / Phase B), legends (0.3). Live-item-on-Element,
construction-time hooks, cross-backend overlay — **non-goals** ([D58]).

---

## 1. DP1 — Make §3.4 real (honor-or-warn), honestly

### 1.1 The policy ([D51])

Spec §3.4 already defines three option classes (`REQUIRED` / `RECOMMENDED` /
backend-specific). 0.2 makes the **recommended** path real, per the chosen policy:

- **Honor where the backend reasonably can** — wire the trivial drops so they are *not*
  falsely reported "unsupported" (§1.2).
- **Warn-and-degrade where it genuinely can't / isn't built yet** — log **once** per
  `(backend, element_type, option)`, then proceed with current behavior. **Never
  raise.** This keeps running code running (the explicit choice over fail-fast).
- **Deprecate, don't delete, dead surface** — `Options` and other accept-then-ignore
  fields emit a `DeprecationWarning` pointing at the live replacement; removal is
  post-1.0 (consistent with the non-breaking stance).

### 1.2 Honor the trivial drops (so the warning is truthful)

These are one-to-few-line wirings; doing them means the warn path only fires for *real*
gaps:

| Option | Backend(s) to wire | Where |
|--------|--------------------|-------|
| `Scatter.marker` → symbol | pyqtgraph (`symbol=`), matplotlib (`marker=`), webengine (`marker.symbol`) | `*/_renderers.py` scatter, `webengine/_figure.py:_scatter_trace` |
| `Scatter.alpha` | pyqtgraph (`brush.setAlphaF`) — mpl/web already honor | `pyqtgraph/_renderers.py:67-69` |
| `Curve.line_style` + `alpha` | pyqtgraph (Qt pen style + alpha) — mpl/web already honor | `pyqtgraph/_renderers.py:79-84` |
| `Image.interpolation` | matplotlib (`imshow(interpolation=)`), pyqtgraph (`ImageItem` opts) | `matplotlib/_renderers.py:144`, `pyqtgraph/_renderers.py:121` |

### 1.3 Warn-and-degrade the genuinely-unbuilt

These have no implementation yet; 0.2 makes them *honest* (warn once, keep current
behavior), and the **feature** lands later:

- `Heatmap.aggregator` — still "last value wins"; warn `"aggregator not yet honored;
  duplicate (x,y) cells use last-value-wins"`. Real reduction → **0.4**.
- `Bars.group` — still a single bar series; warn `"group not yet honored; grouped/
  stacked bars not implemented"`. Real grouped bars → **0.4**.

### 1.4 The mechanism (general, not per-option)

Per `feedback_abstractions` — a *general* seam, not seven special cases:

- Each backend declares, per element type, the set of **recommended options it honors**:
  `honored_options: dict[type, frozenset[str]]` on the `Backend` (or derived from the
  renderer). Default: empty (everything warns) — so the conformance test (§3) forces
  each backend to *positively declare* what it honors.
- One shared helper `core/_degrade.py::check_recommended(element, backend) -> None`
  invoked once per element at the dispatch seam (`_render_element`), comparing the
  element's set `RECOMMENDED_OPTIONS` (filtered to non-default values actually set)
  against `honored_options`, and `warnings.warn(...)`/logging **once** per
  `(backend, type, option)` key (module-level `set` guard, mirroring the existing
  throttle's once-semantics).
- Backend-specific namespaced fields (`pyqtgraph_*`, `matplotlib_*`) are excluded by
  convention (§3.4 class 3).

### 1.5 Capability honesty ([D52])

A declared `Capabilities` field must be backed by a real code path (the negotiation
contract assumes capabilities don't lie):

- `dimensions` → `{2}` on **all** backends until a 3-D renderer exists (today mpl &
  webengine declare `{2,3}` with no 3-D renderer; `dimensions` is currently read by
  nothing, so this is a pure honesty fix). `[D58]` records 3-D as a non-goal for now.
- `animation` → audit: mpl/webengine declare `True` but there is no animation API
  (§12 lists it out of scope) — set to `False` until one exists.
- `exports` — pyqtgraph *under*-claims (`{png}` though SVGExporter exists); leave as-is
  (under-claiming is safe) but note it.
- Add a **capability-honesty conformance test** (§3): each declared boolean/set
  capability must have a corresponding implemented path or be excluded.

### 1.6 Deprecate dead surface

- `Options` (the orphaned `color/alpha/palette/label` type) — `DeprecationWarning` on
  construction ("per-element fields supersede `Options`; see Scatter/Curve/…");
  keep importable through 1.0, then remove. (Removing now would be a breaking change,
  inconsistent with the honor-or-warn stance.)
- `Options.label` / `OverlayOptions.legend` are read by nothing — **wiring** them is
  part of **0.3 legends** (DP5), not here; for 0.2 they're covered by the same
  deprecation/known-gap note so they're not silent.

---

## 2. DP3 — The native escape valve ([D53])

### 2.1 The accessor

The chosen shape (over construction-time hooks): a **post-render accessor** that hands
back the live backend primitive by element id.

```python
class RenderHandle:
    def native(self, element_id: ElementId) -> BackendPrimitive | None:
        """The live backend object for an element (pg.PlotItem, mpl Artist/Axes,
        or the webengine figure handle), or None if unknown / not yet rendered.
        Non-portable by design: the returned type is backend-specific."""

class View(QWidget):
    def native(self, element_id) -> BackendPrimitive | None:
        """Convenience → self.handle.native(element_id)."""
```

`CompositeRenderHandle.native` fans out to child handles (first non-None wins; ids are
unique).

### 2.2 Why this preserves purity (R1)

The live object is produced by the backend and returned *through the handle at/after
render* — it is **never stored on the immutable Element**. So the purity / value-hash
invariant is untouched: no Qt in the element module, elements stay hashable and
value-equal, the negotiation/render caches are unaffected. This is the same resolution
HoloViews uses (`.opts(hooks=...)`), minus putting anything on the spec object.

### 2.3 What it unblocks

The escape valve directly relieves the interaction ceiling (D-cluster) and the escape-
hatch asymmetry (E-cluster) without widening the portable contract:

- Add a pyqtgraph `ROI` / `InfiniteLine` / crosshair / `LinearRegionItem` to a rendered
  element's `ViewBox`.
- Connect any native signal (`sigClicked`, `sigRangeChanged`, mpl callbacks) the
  5-event bus doesn't expose.
- Reach a Bokeh/Plotly `RawFigure`'s underlying object for library-specific work
  (incl. the `ColumnDataSource` row identity the typed events drop).

Documented loudly as **non-portable**: code using `native(...)` opts out of "swap the
backend, same behavior."

### 2.4 Implementation seam

Each backend already builds primitives in `_render_element`; retain an
`element_id → primitive` map on the `RenderHandle` as elements render (pyqtgraph
already threads `element.id` to `attach`; mpl/webengine add the same). `native()` is a
dict lookup. The map rebuilds on `update()` / `set_backend()` — `native()` always
reflects the current handle.

---

## 3. Test plan (TDD — write first, per cadence)

**Tier-1 (pure, no Qt):**
- `check_recommended`: an element with a non-default recommended option a backend does
  **not** honor → exactly one warning per `(backend, type, option)`; honored option →
  no warning; default-valued option → no warning (so `Scatter()` is silent).
- capability honesty: a property test asserting each backend's declared
  `dimensions`/`animation` has an implemented path (table-driven against a registry of
  "what's real").

**Tier-2 (offscreen render, all backends) — the durable guard:**
- **Conformance: honored-or-warned.** For every element type × every declared
  `RECOMMENDED_OPTION`, set a non-default value and assert *either* the output changes
  (honored) *or* a warning fires (degraded). This is the test that stops silent drops
  from ever returning — it would have failed on `marker`, `aggregator`, etc.
- **Honor regressions:** `Scatter(marker="square")` renders a non-circle on each
  backend; pyqtgraph `Scatter(alpha=.3)` / `Curve(line_style="dashed")` visibly differ
  from defaults; `Image(interpolation=...)` differs.
- **Warn regressions:** `Heatmap(aggregator="sum")` / `Bars(group=...)` each emit one
  warning and still render.
- **`native(id)`:** returns the live primitive of the expected backend type for each
  element on each backend; `None` for an unknown id; returns a fresh primitive after
  `update()`; fans out correctly through a `CompositeRenderHandle`.

**Tier-3 (webengine, display-gated):** `native(id)` returns the figure handle; a
`RawFigure`'s native object is reachable.

---

## 4. Benchmarks (establish before/after, per cadence)

The mechanism runs on every render; prove it's free. `benchmark`-marked
(`tests/qtviz/benchmarks/test_bench_degrade.py`; opt-in via `-m benchmark`).

- **`check_recommended` overhead** — the §3.4 check per element (all-honored steady
  state: the `opt in honored` short-circuit, no warn). Target **microsecond-scale**.
- **`native` map build + lookup** — the `element_id → primitive` map is O(elements)
  of references already held by the widget tree; `native()` is a dict get.

**Measured** (offscreen, dev machine):

| What | Result |
|------|--------|
| `check_recommended`, all-honored path | **~0.16 µs / element** |
| `native()` lookup | **~0.06 µs / call** (dict get) |
| render a **200-element** overlay (context) | ~172 ms |

So the contract check costs **~0.16 µs × N** — for the 200-element overlay that is
~32 µs, **≈0.02%** of render time — and the native map adds only N references + an
O(1) lookup. The seam is free; both are far under their ceilings (20 µs / 5 µs).

---

## 5. Acceptance

1. Setting any element option either changes the render or emits exactly one warning —
   verified by the conformance test across all element×option×backend triples.
2. `Scatter.marker`, pyqtgraph `alpha`/`line_style`, `Image.interpolation` are honored.
3. `Heatmap.aggregator` / `Bars.group` warn-and-degrade (don't raise, still render).
4. No backend declares a capability without an implementing path.
5. `qtviz.Options` emits a `DeprecationWarning`; nothing else in the public surface is
   accept-then-ignore without a warning.
6. `view.native(element.id)` returns the live backend object on all three backends; the
   docs show adding a pyqtgraph crosshair via it.
7. Full suite green; ruff clean; benchmarks within targets.

---

## 6. Risks

| # | Risk | Mitigation |
|---|------|------------|
| 1 | Warn-once becomes warn-spam under reactive re-render | key the guard on `(backend, type, option)`, process-lifetime `set`; test re-render fires no new warnings |
| 2 | Wiring a "trivial honor" subtly changes existing goldens | land honors behind the conformance test; pin pre/post on the unchanged-default path |
| 3 | `native()` tempts portable-code misuse | doc it as explicitly non-portable; type as `BackendPrimitive` (opaque); examples are clearly backend-specific |
| 4 | `honored_options` drifts from reality over time | the conformance test *is* the anti-drift guard — a newly-declared recommended option fails until honored or accepted as warned |
| 5 | Deprecating `Options` annoys existing users | pre-1.0 alpha + `DeprecationWarning` (not removal); CHANGELOG note |
