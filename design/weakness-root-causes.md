# qtviz — architectural root causes of the 0.1 weaknesses

> **Purpose.** `developer-perspective-weaknesses.md` is the *what* — the gaps a
> developer feels routing through qtviz instead of using matplotlib / pyqtgraph /
> bokeh / plotly / holoviews directly. **This document is the *why and where-from*:**
> it traces every weakness to the specific invariant, design decision (`[D#]` in
> `discussion-items.md`), or code seam that produces it, classifies each as
> *intrinsic / deferral / incidental / spec-violation*, and turns that into the
> concrete architectural decisions for 0.2+. It is meant as the basis for deciding
> **what, if anything, we change.**
>
> **Method.** Six code-level forensic passes (one per weakness cluster), each tracing
> symptoms to `file:line` and to the decision log, cross-checked against the spec
> spine (`spec.md` §2.1, §2.5–2.7, §2.10, §3.4, §5.5, §7, §12, §13) and
> `axis-surface-feasibility.md`. Every claim below is grounded in the source as of
> `v0.1.0`. Companions: `developer-perspective-weaknesses.md`, `capabilities-gaps.md`,
> `EVALUATION.md`.

---

## 1. Executive summary

Almost every weakness in the companion doc traces to **six root causes**, and they
are not equal: some are the *price of invariants that earn their keep*, and some are
*unforced gaps that cost us nothing to keep paying down.*

1. **R1 — The purity / value-identity invariant.** Elements are pure, immutable,
   Qt-free, value-hashed. Buys headless testability + negotiation/render caching.
   Costs: the escape hatch can't hold a live native object → RawFigure is web-only.
2. **R2 — Lowest-common-denominator vocabulary.** Elements (8), events (5), and
   linear-only axes are the *intersection* across backends. Buys portability. Costs
   breadth and per-backend depth.
3. **R3 — Extensibility asymmetry.** The design's own correctness test is "add a
   *backend*, touch no core file" (§7). Backends and data-adapters are pluggable;
   elements, events, and axis-scales are closed sets. Lifting the R2 ceilings is
   therefore expensive.
4. **R4 — Declared-but-unenforced contracts.** §3.4's honor-or-warn degradation and
   the `Capabilities` record were specified but never enforced — so silent parameter
   drops are the *default*, and some capabilities are aspirational fictions.
5. **R5 — Secondary concerns modeled late / as side-effects.** Axes as a cosmetic
   "surface," legends as a return value of the color-mapping function — neither is
   first-class, so neither generalizes.
6. **R6 — Multi-backend composition has no unified scene.** A layout is N independent
   backend widgets with a merged event bus. Buys mixed-backend dashboards. Costs
   cross-pane legends and composite export.

**The headline for prioritization:** the *most trust-damaging* symptoms (silent
parameter drops, dead API surface, a capability that claims 3-D it can't draw) are
**R4 — spec-violations and incidental gaps**, i.e. mostly *validation and deletion*,
not new features. The *hardest* symptoms (web-only escape hatch, no cross-backend
overlay, no single vector export across backends) are **R1/R6 — intrinsic to
invariants we likely want to keep.** In between sits a band of genuinely valuable,
*additive* work (R2/R3/R5) — an element registry, render-time hooks, an axis-transform
stage, a first-class legend — none of which require breaking an invariant.

---

## 2. The deep structure — six root causes

Each: the invariant/decision (with refs), what it **buys**, what it **costs**
(symptom IDs from §4), and the **lever** that would relax it.

### R1 — The purity / value-identity invariant
*Elements are pure, immutable, Qt-free, value-hashed; `BackendPrimitive = Any` is
"opaque to the core"* (`spec.md:130-131,191-206`; `development-plan.md:21-23`
invariant 1).

- **Buys:** Tier-1 tests run with no `QApplication`; the negotiation cache and the
  `old_root == new_root` render short-circuit key off `Element.__hash__`; reactive
  updates work by *replacing* immutable snapshots; ids are stable enough to persist in
  Studio project files.
- **Costs / produces:** a live `pg.PlotItem`/mpl `Axes` cannot live on an Element — it
  would import Qt into the pure model, be unhashable/mutable, and break value-equality
  (the *same three reasons* `[D38]` used to keep `Signal` off Elements). Hence the
  escape hatch is web-only and can't host native items (**E1, E2, E4**), and there is
  no raw-signal seam on elements (**D4**). Even the *allowed* web `RawFigure` already
  forfeits the benefit: its `figure` field falls to `id()`-hashing (`_immutable.py:36`),
  so it is identity-keyed, not value-keyed.
- **Lever:** a **render-time hook** — hand the live native object to a callback
  *through* `RenderContext` at render time, never stored *on* the Element (exactly
  HoloViews' `.opts(hooks=[...])`). Relaxes the ceiling **without breaking purity**,
  because the live object never touches the immutable model. This is the single
  highest-leverage move (independently surfaced by the interaction *and* escape-hatch
  forensics). → **DP3**.

### R2 — Lowest-common-denominator vocabulary unification
*Elements, events, and axes are the intersection of what all backends share*
(8 elements per `[D4]`; events are "the Phase 1 vocabulary," `spec.md:706`; axes are
linear-only).

- **Buys:** "describe once, swap backend" — the core value proposition.
- **Costs / produces:** the 8-element ceiling (**B1, B5**); the 5-event ceiling and the
  lossy projections that flatten richer native interaction onto it (**D1, D2**);
  `SelectEvent` *is* a rectangle, so a lasso collapses to its bbox (**D3**); linear is
  the only coordinate model all three share, which is half of why axis transforms are
  hard (**C3**).
- **Lever:** **additive widening** preserves portability at an N-backend translation
  cost — new event types, a polygon-shaped `SelectEvent`; and a **partial-support
  tier** lets an element ship on 1–2 backends with a *declared* degradation instead of
  blocking. → **DP2**.

### R3 — Extensibility asymmetry (open at backends/data, closed at elements/events)
*§7/§13 make "adding a backend changes no `core/`, `elements/`, or other-backend file"
the design's stated correctness test.* Backends get a registry + `qtviz.backends`
entry-point; data containers get `register_data_adapter` + a planned
`qtviz.data_adapters` entry-point. **Elements and events get neither** — three
hardcoded `{ElementType: renderer}` dicts plus two import lists, no `register_element`.

- **Buys:** genuinely clean third-party backend and data-container pluggability.
- **Costs / produces:** adding one element (e.g. `BoxPlot`) touches **~8–9 files across
  3 parallel renderers** (**B5**); the LCD ceilings (R2) are expensive to lift because
  there is no registration seam to lift them through (**B1, B2**).
- **Lever:** an **`ElementRegistry` + `qtviz.elements` entry-point** mirroring the two
  registries that already work; the per-backend `RendererRegistry` (`core/backend.py`)
  is *already* the right per-backend seam — it's just populated eagerly from a frozen
  dict. → **DP2**.

### R4 — Declared-but-unenforced contracts
*The honor-or-warn mechanism and the capability record were specified as data and
never enforced as code.* §3.4 fully designs `REQUIRED_OPTIONS`/`RECOMMENDED_OPTIONS` +
"each backend's renderer logs unsupported recommended options once"; §5.5 specifies
`Heatmap.aggregator`. The class attributes were faithfully declared on every element —
but **no code path reads them at render or negotiation time**, and the conformance
suite only asserts "renderer doesn't crash" (`test_backend_conformance.py:41-49`).

- **Buys:** nothing — this is pure gap; the cure was already designed.
- **Costs / produces:** the entire silent-drop class (**S1–S6**), the dead `Options`
  type (**S7**) and dead `OverlayOptions.legend`/`Options.label` (**F2**), and the
  capability fiction `dimensions={3}` on mpl/webengine with no 3-D renderer (**B4**).
  Because the only contract is "a renderer is a function that doesn't raise," *silently
  dropping a field is the path of least resistance and the default.*
- **Lever:** implement §3.4 (a per-field honored-options check + warn-once), add a
  conformance test that asserts a *declared field actually changes output*, and make
  `Capabilities` honest (implement or drop aspirational flags; delete dead types). The
  **cheapest, highest-trust win in the whole analysis.** → **DP1**.

### R5 — Secondary concerns modeled late or as side-effects
*Axes were modeled as a thin cosmetic "surface"; legends as a return value of the
color-mapping function.* `OverlayOptions` was born with title/labels/legend/background
and **no** scale/limit/tick/aspect concept (`spec.md:406-418`); the resolve pipeline
produces concrete data-space arrays with no transform stage; `Legend` is what
`map_colors` *returns* (`encoding.py:57`), not an element.

- **Buys:** faster initial delivery; de-risked seams (Phase A wired the dead text
  fields first, on purpose).
- **Costs / produces:** no log/datetime/limit/invert axes (**C1, C2, C4**); no legend
  for any non-`color_by` element or multi-series overlay (**F1, F3**), and the stub
  legend flags sit unwired (**F2, F5**).
- **Lever:** an **`AxisSpec` + a coordinate-transform step** threaded via
  `RenderContext` (**DP4**); a **per-element `legend_entry()` contract** aggregated
  across an Overlay's children (**DP5**). Both are additive and live entirely inside
  the *single-surface* path — they touch no invariant.

### R6 — Multi-backend composition has no unified scene graph
*A layout is N independent backend widgets in a Qt container, unified at the event
bus, not the scene* (`core/_host.py`; `CompositeRenderHandle` = N child handles +
merged bus, `core/backend.py:127-154`).

- **Buys:** mixed-backend dashboards at all; Qt-free negotiation; independent backend
  plug-ins.
- **Costs / produces:** no surface on which a cross-pane legend could be drawn
  (**F7**); composite export raises because there is no single canvas (**F6**,
  `[D11]`); cross-backend Overlay is out of scope (`spec.md:1777`).
- **Lever:** a **composite-level coordinator** that stitches per-pane *rasters* and
  draws cross-pane chrome (additive; the merged *event* bus proves the pattern). But a
  single **vector** surface across heterogeneous backends is **genuinely intrinsic and
  not cheaply solvable** — accept it. → **DP6**.

---

## 3. The cross-cutting pattern — "accept-then-ignore"

R4 and R5 share a tell that appears all over the 0.1 surface and is, by itself, the
biggest driver of the "can I trust this?" reaction: **fields and types that are
accepted (and even validated) but read by nothing.**

`Scatter.marker` · `Scatter.alpha`/`Curve.line_style` on pyqtgraph · `Heatmap.aggregator`
· `Bars.group` · `Image.interpolation` · the whole `Options` type · `OverlayOptions.legend`
· `Options.label` · `Capabilities.dimensions={3}` · the webengine `_legend` that is
computed then discarded (`_figure.py:74,293`).

The root is structural, not careless: the framework has **type-granularity but no
field-granularity** in either its capability model (R4) or its options model (R5), and
nothing — no negotiation check, no conformance test, no public-surface audit —
distinguishes "field honored" from "field ignored." A single mechanism (per-field
honored-options + a conformance assertion + an `__all__` surface test) closes most of
this class at once.

---

## 4. Per-cluster forensics

Columns: **Symptom** · **Root cause** (decision/spec ref) · **Origin**
(`INTR` intrinsic-to-invariant · `DEF` deliberate-deferral · `INC` incidental gap ·
`VIO` spec-violation) · **Code seam** · **Fix shape & blast radius**.

### A — Silent parameter drops & the capability model

| ID | Symptom | Root cause | Origin | Code seam | Fix & blast radius |
|----|---------|-----------|--------|-----------|--------------------|
| S1 | `Scatter.marker` dropped on all 3 backends | No renderer reads `marker`; §3.4 warn-path never built (`marker` is the spec's canonical RECOMMENDED example) | **VIO** | `pyqtgraph/_renderers.py:58-76`; `matplotlib/_renderers.py:53-66`; `webengine/_figure.py` `_scatter_trace` | Honor (map `symbol`/`marker` in 3 renderers) **or** build the §3.4 per-field check; latter touches `capabilities.py`, each caps ctor, one shared checker, conformance suite |
| S2 | `Scatter.alpha` ignored on pyqtgraph | `render_scatter` sets brush w/o `setAlphaF`; `render_spread` *does* (`:219`) → per-renderer omission, not a backend limit | **INC** | `pyqtgraph/_renderers.py:67-69` | 1-line `setAlphaF`; class-fix = S1 net |
| S3 | `Curve.line_style`/`alpha` ignored on pyqtgraph | pen built from color+width only; mpl/webengine honor both | **INC** | `pyqtgraph/_renderers.py:79-84` | map `line_style`→Qt pen style + alpha; class-fix = S1 net |
| S4 | `Heatmap.aggregator` no-op everywhere | every backend does `grid[y,x]=z  # last value wins (aggregator TODO §5.5)`; never reads the field | **DEF+VIO** | `pyqtgraph/_renderers.py:197`; `matplotlib/_renderers.py:206`; `webengine/_figure.py:170` | short term: `_validate` rejects non-default until honored; long term: grouped reduce in 3 renderers |
| S5 | `Bars.group` stored, never read | field exists ahead of grouped-bars feature; no degradation declared | **DEF→VIO** | set `elements/bars.py:33`; consumed nowhere | reject/warn until grouped bars ship; then 3 renderers |
| S6 | `Image.interpolation` never passed | trivially-passable param simply not wired | **INC** | `matplotlib/_renderers.py:144-147`; `pyqtgraph/_renderers.py:121-127` | pass through to `imshow`/`ImageItem`; class-fix = S1 net |
| S7 | `Options(color/alpha/palette/label)` exported but dead | superseded by per-element kwargs (`spec.md:352-354`); never deleted; only self-referential tests | **INC** | `core/options.py:18`; export `__init__.py:31,71` | remove from `__all__`+`options.py`; add a public-surface test |

**Synthesis.** The capability model has **type-granularity, no field-granularity**:
`Capabilities` is a backend-wide bag of flags, negotiation only asks
`backend.supports(type(node))`, and the dispatch seam invokes the renderer as an
opaque function with no post-condition. §3.4 designed the cure (REQUIRED/RECOMMENDED +
warn-once); the attributes were declared on every element but **read by nothing**, and
the conformance suite only checks "doesn't crash" — so a green test run is fully
compatible with six dropped fields. *Dropping a field is the default; honoring it is
opt-in with nothing checking the difference.*

### B — The element-vocabulary ceiling & registry asymmetry

| ID | Symptom | Root cause | Origin | Code seam | Fix & blast radius |
|----|---------|-----------|--------|-----------|--------------------|
| B1 | Closed set of 8; no way to add a 9th without forking | element set is a static import list, not a registry; `[D4]` Phase-1 cut hardened into a structural limit | **DEF** | `elements/__init__.py:5-19`; 3 dispatch dicts (`_renderers.py:226`, `:229`, `_figure.py:206`) | `ElementRegistry` + `qtviz.elements` entry-point (mirrors backends/data) |
| B2 | 3rd parties can add backends & data adapters, not elements | registry+entry-point applied to 2 of 3 plug-in axes; never to elements; no decision ever rejected it | **INC** | registries at `data/registry.py:31`, `backends/__init__.py:15`; element peer missing | same registry; low blast for the seam itself |
| B3 | An element only one backend can draw can't be overlaid | one-meaning invariant + `auto_negotiate` needs one backend supporting *every* overlay child (`[D4]`) | **INTR** | `core/compose.py:152-159`; degradation `spec.md:1073-1094` | partial-support/declared-degradation tier; changes negotiation contract (medium) |
| B4 | `dimensions={3}` declared on mpl/webengine, no 3-D renderer | dead metadata — `dimensions` is **read by zero consumers**; flag describes substrate, not qtviz capability | **VIO** | `capabilities.py:11`; `matplotlib/render.py:33`; `webengine/render.py:33` | honest fix today: set `{2}`; real 3-D = parallel render path (large) |
| B5 | Adding one element ≈ 9 files, 3 renderers | no registry (B2) × one-meaning (B3) | **INTR+INC** | element class + 2 `__init__` + 3 renderers + 2 registry dicts + adapter branch + tests | registry collapses the `__init__`/dict edits; partial-support lets author write 1 renderer not 3 |

**Synthesis.** A deliberate two-axis extensibility design (open at *backends* and
*data containers*) that **omitted the third axis** (*elements/events*). Half
intentional — the closed vocabulary was an explicit `[D4]` scoping choice, and the
one-meaning invariant makes every element a cross-backend contract, so an open element
registry was genuinely *harder* to offer than an open backend registry. But the
absence of even a *closed-but-registerable* mechanism, and the `dimensions={3}`
fiction, are unforced. The architects wrote the "add a backend without touching core"
test (§7) and never wrote its symmetric twin for elements.

### C — Axis transforms & the coordinate/data pipeline

| ID | Symptom | Root cause | Origin | Code seam | Fix & blast radius |
|----|---------|-----------|--------|-----------|--------------------|
| C1 | No coordinate-transform stage exists | resolve pipeline only resolves accessors + rasterizes; hands concrete float64 data-space arrays straight to primitives | **INTR** | `data/pipeline.py:95-116`; `_renderers.py:33-34,70,82`; `RenderContext` has no scale (`backend.py:34-40`) | add `x_scale`/`y_scale` to `RenderContext`, resolved once in `_render_cell`; `_logify` in 5 x/y renderers |
| C2 | `apply_surface` is cosmetic (title/labels only) | `OverlayOptions` born without scale/limit/tick concept; Phase A intentionally wired only text fields | **DEF** | `core/options.py:37-54`; `pyqtgraph/_surface.py:12-19`; `matplotlib/_surface.py:12-19` | add `AxisSpec` + extend `OverlayOptions`; "one-line native calls" per backend (feasibility ✅) |
| C3 | One `scale="log"` = three coordinate models | pyqtgraph bare items ignore `setLogMode` → ViewBox enters exponent space; mpl stays data-space; Plotly log-space only at relayout (risk **R1**) | **INTR** | `pyqtgraph/render.py:55-68`; `_interaction.py:43-75`; `_events.py:20-32`; `webengine/_translate.py:162-173` | pre-`log10` data + `AxisItem.setLogMode`; `10**`/`log10` at every event/state boundary; ~120-150 LOC pyqtgraph, ~1 line mpl, small webengine |
| C4 | Limits settable only inside zoom-state restore | `ViewState`/`restore_state` added for pan/zoom persistence (`[D2]`); no declarative `AxisSpec.lim` | **INC** | `pyqtgraph/render.py:67`; `matplotlib/render.py:66` (both in `restore_state`) | `AxisSpec.lim/invert/aspect`; set initial range in `apply_surface`; existing `_install` ordering lets live pan/zoom win |
| C5 | Datetime axes unrepresentable end-to-end | data layer carries no datetime dtype through resolve/accessors/events; translator bails | **DEF** | `webengine/_translate.py:172` (`return None # datetime — not wired in W1`) | accept `scale="time"` in seam now; gate render on data-layer datetime dtype (separate) |

**Synthesis.** "Describe once, render across three backends with *three incompatible
coordinate models* for the same concept" is what makes axis transforms structurally
harder for qtviz than for any single library: the transform must be implemented once
*and inverted three different ways* to keep `ViewState`-in-data-coords honest (`[D2]`,
risk R1 — the feasibility doc's "single highest-risk item"). The late/thin modeling
was *both* a defensible sequencing choice (Phase A de-risked the seam with the dead
text fields) *and* a genuine early omission (no `AxisSpec`, no transform stage). The
fix is bounded and feasibility-proven — but heavier than a single library's one-liner.

### D — The interaction ceiling & event normalization

| ID | Symptom | Root cause | Origin | Code seam | Fix & blast radius |
|----|---------|-----------|--------|-----------|--------------------|
| D1 | All interaction = 5 typed events; no ROI/crosshair/keyboard/context-menu/double-click | closed, backend-portable contract; `Capabilities` exposes only `picking`/`brush`/`range_events`; the 5 are the cross-backend intersection | **INTR** | `core/event.py:19-55`; `capabilities.py:13-15`; `spec.md:668-717` | widen the enum (new frozen types + N translators + caps flags) — additive, preserves portability |
| D2 | Translators discard native richness | each translator is a lossy projection (`[D27]`): double-tap dropped, surface cell→`None`, Bokeh select→bounds w/ empty indices | **INTR+DEF** | `webengine/_translate.py:38-44,117-129` | Bokeh indices recoverable from `ColumnDataSource` (W3b); double-tap needs a new type |
| D3 | Rect-only select; lasso collapses to bbox | brush is a rubber-band rect (`[D12]`) **and** `SelectEvent.bounds` *is* a rect — no field for a polygon | **INTR+DEF** | `core/event.py:38-40`; `_interaction.py:43-73`; `_translate.py:141-145` | add `region: Polygon\|Rect` + point-in-poly; widens the public event schema (high blast) |
| D4 | No raw-signal passthrough | the 5 typed events are the only exit (`View.on`→bus); `RenderHandle` holds the widget but exposes no per-element native item or signal hook | **DEF** | `core/view.py:209-228`; `core/backend.py:59-77` | **`handle.native(element_id)` / `View.hooks`** — additive, leaves the contract intact; highest-leverage relaxation |
| D5 | No pixel→source-rows through a raster | aggregation is destructive: only per-pixel scalars kept (`value_at`→value, never indices); `[D46]` scoped row-id out | **INTR+DEF** | `ext/datashader.py:50-76,128-156`; `event.py:37-48` | data-space *predicate* selection via a `DataSource` w/ pushdown (Phase 5); large, blocked on the source layer |

**Synthesis.** The *same* LCD-portability logic that bounds the element vocabulary
bounds the event vocabulary — every translator is a lossy projection onto five fixed
types. For the *contract* this is intrinsic (a portable event can't carry
library-specific gestures; an out-of-core aggregate can't carry row identity). The one
genuinely relaxable-without-cost facet is **D4**: a `.hooks`-style native passthrough
on the `RenderHandle` (which already holds the live widget) lets developers opt into
non-portable backend signals knowingly, leaving the 5-event LCD intact for everyone
else. The rest are additive widenings (new event types, polygon select) at N-backend
cost; only raster row-id is hard-blocked on a `DataSource` layer that doesn't exist.

### E — The escape hatch (RawFigure) & the purity invariant

| ID | Symptom | Root cause | Origin | Code seam | Fix & blast radius |
|----|---------|-----------|--------|-----------|--------------------|
| E1 | RawFigure renders only on webengine | born in the webengine rehome as a host for *web* figure libs; `kind ∈ {plotly,bokeh,holoviews}` (`[D26]/[D31]`) | **DEF+INTR** | `webengine/render.py:136-138,170-182` | a web-only host is the only host this element *can* have (payload is an inert spec) |
| E2 | Can't host a live mpl `Axes`/pg `PlotItem` | native `supports()` is registry-driven; RawFigure unregistered → `RendererMissingError` (deliberate, `[D26]`) | **INTR** | `pyqtgraph/render.py:159-162`; `matplotlib/render.py:157-160` | needs a *different* seam (E4), not an extension of RawFigure |
| E3 | RawFigure can't compose (Overlay raises) | a foreign whole-figure has no trace-level decomposition to merge into the one-Plotly-figure model (`[D31]`) | **INTR+DEF** | `webengine/_figure.py:243-246`; `render.py:140-142` | unfixable for foreign figures; native hooks (E4) sidestep it |
| E4 | Purity forbids a live-item element (no `.opts(hooks)` analog) | invariant 1: a live `PlotItem` would import Qt, be unhashable/mutable, break value-eq — the same 3 reasons `[D38]` barred `Signal` | **INTR** | `_immutable.py:30-38,75-91`; `development-plan.md:21-23`; `raw_figure.py:36` | **render-time hook through `RenderContext`**, never on the Element — bends value-eq for one opt-in field only; small blast |
| E5 | Bokeh/HoloViews RawFigures lose Pick + select-indices | W3b unbuilt (`[D32]`); a foreign figure's row identity is outside qtviz's resolve pipeline | **DEF+INTR** | `webengine/_translate.py:117-127,38-44` | finish the `bokeh.*` map (W3b); row-id needs live-source reach-in only a hook can give |

**Synthesis.** One invariant doing double duty. The purity/value-hash model is what
buys headless testability and hash-keyed caches — *and* the same property makes the
only escape hatch web-only and all-or-nothing. A foreign **web** figure can sit on an
Element only because it is an inert spec (and even then it is opaquely `id()`-hashed,
already forfeiting the benefit); a live **native** item cannot sit on an Element at
all. The resolution is the one HoloViews chose: never put the live object *on* the
Element — hand it to a callback *at render time through the backend* (E4), bending
value-equality for that one opt-in field while leaving the pure core intact. **This is
the central architectural tension of the whole library.**

### F — Legend poverty, export poverty, and the composition model

| ID | Symptom | Root cause | Origin | Code seam | Fix & blast radius |
|----|---------|-----------|--------|-----------|--------------------|
| F1 | Legend only from `color_by`/raster | `Legend` is the *return value* of `map_colors`, not an element; `[D23]` deferred legend-as-element | **DEF** | `core/encoding.py:28-39,57` | per-element `legend_entry()` contract; touches `element.py`, 8 elements (+`label`), 3 legend builders |
| F2 | `OverlayOptions.legend`/`Options.label` do nothing | stub fields never wired (accept-then-ignore, §3) | **DEF+INC** | `core/options.py:46,52,32` | wire `legend`(+`legend_position`) through `surface_of`→`apply_surface`; cheap |
| F3 | Multi-series Overlay has no legend | renderers return artists; no "each element contributes an entry" pass over `Overlay.children` | **INTR** (to F1's modeling choice; *not* to composition — an Overlay is single-surface) | `pyqtgraph/render.py:153-155`; `matplotlib/render.py:151-153` | aggregate `legend_entry()` after the children loop; highest-value, single-surface |
| F4 | pyqtgraph colorbar = 5-stop swatch, not gradient | reused the `LegendItem` swatch path to avoid fragile `GradientLegend` positioning (dep *ships* `ColorBarItem`/`GradientLegend`) | **DEF/INC** | `pyqtgraph/_legend.py:5-7,38-41`; stops `encoding.py:25` | swap continuous branch to `pg.ColorBarItem`; local to `_legend.py`; closes mpl-parity gap |
| F5 | webengine renders no legend for anything | `showlegend:False` hardcoded; computed `_legend` discarded (`[D50]` deferral) | **DEF** | `webengine/_figure.py:293,74` | `showlegend:True` + per-trace `name` (already set) + colorbar from discarded `_legend`; cheapest of the set |
| F6 | Composite/mixed-backend export raises | `CompositeRenderHandle.export` raises (`[D11]` opt c) — no single surface across N backend exporters | **INTR+DEF** | `core/backend.py:150-154` | (a) `widget.grab()` whole container → one PNG; (b) per-pane export list. **Single *vector* surface = intrinsic** |
| F7 | No unified scene graph across panes | composition is N independent backend widgets in a Qt container; events merged, scene not (foundational, Qt-free negotiation) | **INTR** | `core/_host.py:50-117`; `core/backend.py:127-154` | composite-level coordinator stitches per-pane rasters + cross-pane chrome; additive, raster-only |

**Synthesis.** Legends and export fail for the *same structural reason* — composition
is "N independent backend widgets with a merged event bus," so there is no common
surface for cross-pane chrome or a single export. That part (**F6, F7**) is **intrinsic
to multi-backend composition** and was ratified as a Phase-1 deferral (`[D11]`).
Independently and far more cheaply fixable is an **incidental modeling choice**:
`Legend` is the return value of the color-mapping function rather than a first-class
element with a per-element contribution contract — which is why every non-`color_by`
element and every multi-series Overlay gets no legend, and why the stub flags sit
unwired. The legend cluster (F1–F5) is resolvable inside the single-surface Overlay
path with an element-level legend contract + wiring; only cross-pane legend and
composite *vector* export are truly intrinsic.

---

## 5. Origin-type ledger

Every symptom, classified — this is the cut that says *what is cheap vs. what requires
a deliberate invariant decision.*

| Origin | Count | Symptoms | What it means for us |
|--------|-------|----------|----------------------|
| **VIO** — spec-violation | 4 | S1, S4(also DEF), S5(also DEF), B4 | We're *already supposed* to do this. Cheapest credibility wins; mostly validation. |
| **INC** — incidental gap | 8 | S2, S3, S6, S7, B2, C4, F2, F4 | Unforced; small, local fixes. No invariant in the way. |
| **DEF** — deliberate deferral | 11 | S4, S5, B1, C2, C5, D2, D4, E1, E5, F1, F5 | Roadmap choices. Re-decide per value, not per difficulty. |
| **INTR** — intrinsic to an invariant | 11 | B3, B5, C1, C3, D1, D3, D5, E2, E3, E4, F3, F6, F7 | Require a conscious "keep the invariant (pay the cost) or relax it (and how)" decision. |

*(Several symptoms are dual-origin — listed under each that applies.)* The
distribution is the actionable message: **~12 symptoms are spec-violations or
incidental gaps** (cheap, no invariant tension), **~11 are deferrals** (roadmap value
calls), and **only a hard core is genuinely intrinsic** — and most of *those* have a
purity-preserving lever (E4/D4 hooks) or a partial-relaxation (B3 partial-support).

---

## 6. Decision points for 0.2+

Framed as forks, because that's what this document is for. Each: what it does, which
root it relaxes, blast radius, recommendation.

**DP1 — Enforce the contracts (fixes R4). _Recommended: yes, first._**
Wire §3.4 (a per-backend `honored_options` set + one shared warn-once checker at the
dispatch seam), add a conformance test that asserts a *declared field changes output*,
make `Capabilities` honest (`dimensions={2}` until a 3-D renderer exists; drop or
implement off-thread), and delete the dead `Options` type. Mostly *validation and
deletion*. Closes S1–S7 + B4 + F2. Blast radius: `capabilities.py`, each backend's
caps + a few renderer lines, one shared checker, the conformance suite, `__init__`
`__all__`. **The highest trust-per-effort move in the analysis.**

**DP2 — Element registry + partial-support tier (relaxes R2/R3).**
Add an `ElementRegistry` + `qtviz.elements` entry-point (mirroring backends/data), and
a declared-degradation tier so an element can ship on 1–2 backends and *declare*
"unsupported on webengine" instead of blocking an Overlay. Unlocks vocabulary growth
(Box/Violin, grouped bars, …) and third-party elements. Blast radius: medium — it
changes the negotiation contract (`compose.py` overlay-intersection, error taxonomy).

**DP3 — Render-time hooks (`handle.native(element_id)` / `View.hooks`) (relaxes R1, D4).**
Hand the live `PlotItem`/`Axes`/figure to an opt-in callback *through* `RenderContext`
at render time, never stored on the Element. Gives developers ROIs, crosshairs, native
signals, and Bokeh-source row access — *without breaking purity* (the live object never
touches the immutable model; one opt-in field is identity-keyed, like callable
accessors already are). Blast radius: small — a `RenderContext`/`RenderHandle`
accessor + each backend retaining an `element_id → native item` map (pyqtgraph already
threads `element.id`). **The single highest-leverage relaxation; recommended.**

**DP4 — First-class axes: `AxisSpec` + transform stage (relaxes R5-axes).** *(= roadmap Phase B.)*
`OverlayOptions` gains `x`/`y` `AxisSpec` (scale/lim/invert/tick_format) + `aspect`;
`RenderContext` gains `x_scale`/`y_scale`; renderers apply a `_logify` helper; pyqtgraph
gets the R1 boundary normalization (~120–150 LOC, feasibility-proven). Datetime gated
on the data layer (C5). Already spiked; ready.

**DP5 — First-class legends: `legend_entry()` + Overlay aggregation (relaxes R5-legends).**
Per-element legend contribution (swatch + label); aggregate across `Overlay.children`;
wire the existing `OverlayOptions.legend` + a position field; flip webengine
`showlegend:True` (cheap); swap pyqtgraph to a true `ColorBarItem`. High value, low–medium
blast, entirely inside the single-surface path. (F3/F5 are the cheap, high-value start.)

**DP6 — Composite coordinator for cross-pane chrome + export (partially relaxes R6).**
A composite-level coordinator that stitches per-pane rasters (PNG composite export via
`widget.grab()`; optional per-pane list) and can draw cross-pane legends. **Accept the
limit:** a single *vector* surface across heterogeneous backends is intrinsic and not
in scope. Blast radius: medium, additive.

**DP7 — Keep deferred / forbidden (a decision to *not* build).**
Cross-backend Overlay (R6) and live-item-on-Element (R1) are genuinely intrinsic;
recommend **not** pursuing them — DP3 hooks + DP6 coordinator cover the real needs at a
fraction of the cost and risk. Raster pixel→rows (D5) stays blocked on the Phase-5
`DataSource`/pushdown layer; sequence it there, not here.

---

## 7. What to keep (the invariants worth their cost)

The analysis is not an argument to dismantle the architecture — most of what it costs,
it earns back:

- **Purity / value-hash (R1)** — keep. It is the foundation of headless testing, the
  negotiation/render caches, and reactive snapshots. Relax it *only* via render-time
  hooks (DP3), never by putting live state on Elements.
- **LCD portability (R2)** — keep. It *is* the product. Widen it additively (DP2/DP4/
  new event types); don't fork per-backend semantics into the core.
- **Backend & data extensibility (R3)** — keep, and *extend the same pattern to
  elements* (DP2). The asymmetry, not the registries, is the problem.
- **Multi-backend composition (R6)** — keep. Mixed-backend dashboards are a genuine
  differentiator. Add a coordinator (DP6); accept no unified vector surface.

The throughline: **the invariants are sound; the gaps are (a) contracts we specified
and never enforced, (b) one extensibility axis we never opened, and (c) two
first-class concepts (axes, legends) we modeled as afterthoughts.** None of those
require breaking what makes qtviz qtviz.

---

## 8. Weakness → root → decision map

The companion doc's weaknesses, tied to roots and the decision that addresses each.

| Weakness (companion §) | Symptoms | Root(s) | Origin | Decision |
|------------------------|----------|---------|--------|----------|
| Silent param drops (1.1) | S1–S7 | R4 | VIO/INC | **DP1** |
| Element ceiling / no 3-D (1.2) | B1–B5 | R2, R3 | DEF/INC/INTR | **DP2** (+DP1 for B4) |
| No axis transforms (1.3) | C1–C5 | R5, R2 | DEF/INTR/INC | **DP4** |
| Interaction ceiling (1.4) | D1–D5 | R2, R1 | INTR/DEF | **DP3** (+DP2 widening; D5→Phase 5) |
| Legend poverty (1.5) | F1–F5 | R5 | DEF/INC/INTR | **DP5** |
| Export poverty (1.6) | F6 | R6 | INTR/DEF | **DP6** |
| Escape-hatch asymmetry (1.7) | E1–E5 | R1 | INTR/DEF | **DP3** (+DP7 keep-deferred) |
| Double learning curve / ecosystem (1.8) | — | *non-architectural (maturity/time)* | — | docs/recipes/stability, not code |

**Bottom line for the architecture review:** do **DP1** now (cheap, fixes the
trust-eroding class), commit to **DP3** as the strategic relaxation (purity-preserving
escape valve that unblocks interaction *and* native escape hatches at once), and
sequence **DP4/DP5** as the additive first-class-concept work. **DP2** is the bigger
structural bet (open the element axis); **DP6** and **DP7** define the edges of what
multi-backend composition can and won't do.
