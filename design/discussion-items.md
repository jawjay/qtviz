# qtviz — discussion items

> Open design tradeoffs and challenges surfaced while writing
> `development-plan.md`. Each is something to **decide before or during the
> milestone that needs it** — not a blocker on starting. Referenced from
> the plan as **[D#]**.
>
> Format: **Context** (why it exists) · **Options** · **Recommendation** ·
> **Blocks** (which milestone) · **Status**. Update Status as we resolve;
> resolved items graduate into `spec.md` §11.
>
> Distinct from `spec.md` §11 "Currently open" (Q-O, Q-P), which are
> narrower. The two cross-reference; don't duplicate.
>
> **Disposition (this revision).** [D1] is **resolved** and folded into
> spec §2.1/§6. [D2]–[D11] are **accepted as recommended** but parked —
> each flagged to revisit at the milestone that needs it (see the Index).
> Nothing in D2–D11 blocks starting M0–M2.

---

## [D1] Data layer — container-agnostic, lazy-first  ✅ RESOLVED

**Decision.** Option B's spirit, scaled up: **not** a thin columnar shim but
a **pluggable data subsystem** shaped like the backend registry — because
the library runs in data-intensive settings and users bring diverse, often
out-of-core containers. Folded into `spec.md` §2.1 (the `DataRef` contract)
and §6 (the architecture).

**What was decided.**
- **Two shapes, one contract:** `TabularRef.series(name)` and
  `GriddedRef.grid(value)` → numpy; renderers resolve fields by *name* and
  never branch on the container.
- **Lazy-first:** cheap metadata (`schema`/`size`/`extent`/`select`/
  `window`/`fingerprint`) is sync on the GUI thread; one expensive
  `materialize` runs on a Worker; the pipeline narrows (projection + window,
  pushed **down** into the container) before it pulls, so out-of-core data
  is never fully materialized just to draw a viewport.
- **Adapter registry** (mirrors backends): optional adapters auto-register
  iff their library imports; third parties via a `qtviz.data_adapters`
  entry-point. Ship the contract + eager adapters now; each new container is
  one additive adapter file.
- **`native()` escape hatch** feeds Datashader the raw lazy object — no
  dense-ndarray round-trip.

**Explicitly planned at the abstraction level (not Phase-1 dependencies):**
xarray, zarr, dask.array / dask.DataFrame, and the Phase-5 query
`DataSource`. Roadmap table in spec §6.3.

**Residual sub-questions to revisit later (don't block M1):**
- *Gridded shape-bridging* — exactly when a `GriddedRef` may serve a tabular
  Element (1-D dim→x, values→y) vs must raise. Pin down with the first real
  xarray adapter.
- *`extent` aggressiveness* — for lazy refs, how hard to try for true
  min/max on initial axes vs return `None` and auto-range on the
  materialized slice. Correctness/latency tradeoff; settle with the dask
  adapter.
- *`window` semantics across shapes* — index-range vs coordinate-range
  slicing, and how a backend's `RangeEvent` maps back to a `window` call for
  viewport-driven re-aggregation (Phase 4).

**Blocks.** Contract frozen at M1; lazy adapters Phase 4–5.
**Status:** ✅ resolved → spec §6; residuals tracked above.

---

## [D2] `ViewState` — should it be in the core `RenderHandle` contract?

**Context.** `handle.update()` (Phase 1 = full rebuild) and
`view.set_backend()` both tear down and rebuild primitives. Naively, both
reset zoom/pan/selection to data bounds. For reactive updates (Phase 4)
and for backend switching (Phase 1, §3.5) that's a visible regression — the
user zooms in, the data ticks, and the view jumps back out.

**Options.**
- **A. Add `capture_state()/restore_state()` to `RenderHandle` now.** Every
  backend implements a `ViewState↔native` mapping. Pro: solves it once,
  uniformly; makes cross-backend switch preserve zoom. Con: every backend
  carries the mapping from day one; cross-backend range semantics aren't
  perfectly equal (log axes, categorical axes).
- **B. Defer; accept reset in Phase 1, add when reactive lands.** Pro: less
  Phase 1 surface. Con: set_backend (a Phase 1 feature) ships with the jump
  bug; retrofitting touches every backend later anyway.
- **C. Capture only ranges (not selection) in Phase 1.** Middle ground.

**Recommendation.** **A, ranges-first (C-then-A).** Fold `capture/restore_
state` into the spec's `RenderHandle`. Selection portability can lag.
Rationale: it's cheaper to define the seam before two backends exist than
after.

**Blocks.** M3 (handle), M5 (set_backend). **Status:** accepted (ranges-
first) — apply the spec §2.8 addition at M3; revisit selection portability
later.

---

## [D3] The `materialize` pass — placement and re-entrancy

**Context.** In-memory `snapshot()` is sync; `DataSource.snapshot()`
(Phase 5) returns a `Future`. Renderers must only ever receive concrete
data, so something must resolve refs *before* `render`. The plan inserts a
`materialize(node)` phase between negotiate and render.

**Open questions.**
- Where does it live — `View`, or a `pipeline` helper in `compose`/`view`?
- Async UX: while a Future is pending, show a placeholder widget? a spinner
  overlay? leave the old render up? Re-entry on resolve must not race a
  newer `set_root`.
- Does materialize run per-node (parallel Workers for a multi-source
  Layout) or whole-tree?

**Recommendation.** Phase 1: `materialize` is the **identity function** but
present in the pipeline (`View._build = negotiate → materialize → render`).
Defer async semantics to Phase 5; record the seam now so `View` doesn't get
reshaped later. Tie re-entry to a monotonic build-id so stale Futures are
dropped.

**Blocks.** Pipeline shape at M5; full behavior Phase 5. **Status:**
accepted — wire the (no-op) seam at M5; revisit async/placeholder behavior
when lazy adapters land (Phase 4–5). Now load-bearing for [D1]'s lazy refs.

---

## [D4] Auto-Overlay correctness — "supports-all-children", not "best-per-child"

**Context.** `spec.md §3.3 auto_negotiate` collapses an Overlay's children
to `highest_priority(picks)`, where `picks` is each child's individually
best backend. **Bug:** the winner may not support its *siblings*. Example:
child A only on pyqtgraph, child B only on webengine → `picks =
{pyqtgraph, webengine}`, collapse picks pyqtgraph, which can't render B.

**Correct algorithm.**
```python
def auto_overlay_backend(overlay):
    common = [b for b in registered
              if all(b.supports(type(c)) for c in elements_of(overlay))]
    if not common:
        raise IncompatibleOverlayError(            # genuinely impossible
            "no single backend supports all overlay children: ...")
    n = max(data_size(c) or 0 for c in elements_of(overlay))
    pool = common
    if n > 1_000_000:
        return max(pool, key=lambda b: b.capabilities.max_recommended_points)
    return max(pool, key=lambda b: -priority_index(b.name))
```
i.e. **intersect** supported backends across children first, then apply the
size/priority rule within that intersection.

**Recommendation.** Adopt; **update `spec.md §3.3`** to replace the
`picks`/`highest_priority` sketch with the intersect-first version.

**Blocks.** M2. **Status:** accepted — apply the §3.3 intersect-first fix at
M2 (left un-applied in the spec for now, per the revisit-later disposition).

---

## [D5] Threading enforcement — how strict, what cost?

**Context.** Spec §2.14 puts `@require_gui_thread` on *every* renderer plus
the handle/backend/view mutators. That's a wrapper on every hot-path render
call and an import-time decoration of every registered renderer.

**Options.**
- **A. Always on.** Safest; a per-call `is_gui_thread()` check (cheap, but
  non-zero on a 1M-point redraw loop).
- **B. On in debug/tests, off in release** (env flag). Fast hot path; risk
  of a latent off-thread bug shipping.
- **C. Guard mutators only, not leaf renderers.** Renderers are always
  called *by* a guarded `render()`/`update()`, so the entry guard already
  covers them transitively — drop the per-renderer decorator.

**Recommendation.** **C.** Guard the public entry points
(`Backend.render`, `RenderHandle.update/dispose`, `View.set_*`); trust that
renderers only run beneath them. Keep one Tier‑2 test that calls a renderer
off-thread through the public API and asserts it raises. Avoids decorating
24+ leaf functions and keeps the redraw loop clean.

**Blocks.** M4. **Status:** accepted (entry-only guarding) — revisit at M4.

---

## [D6] Rename mechanics — how does qtwebplot physically rehome?

**Context.** `qtwebplot` → `qtviz` (roadmap Phase 0). The existing
webengine code (`core/web_bridge_view.py`, `ext/plotly|bokeh|holoviews`,
`layouts.py`, `theme.py`) must land under `backends/webengine/` *and* keep
working, while a `qtwebplot` shim warns.

**Options.**
- **A. Move now (Phase 0), shim immediately.** All new code is born under
  `qtviz`. Pro: no second migration. Con: churns the working POC before the
  new layers exist to exercise it.
- **B. Build `qtviz` core alongside; rehome webengine last (Phase 5).** The
  spec/roadmap already schedule the webengine rehome at Phase 5. Pro: don't
  disturb working code until its new home (the backend protocol) is real
  and tested. Con: two import roots coexist for months.
- **C. Keep `qtwebplot` as an internal subpackage** under
  `qtviz/backends/webengine/` verbatim, re-exported — minimal edits.

**Open sub-questions.** Does `Theme` (today `qtwebplot.theme`) move to
`qtviz.core.theme` in Phase 0 (it's shared by all backends) while the rest
of webengine waits until Phase 5? That split is awkward — Theme is needed
by pyqtgraph in Phase 1.

**Recommendation.** **B**, but **promote `Theme` early**: migrate
`theme.py → qtviz.core.theme` with the `Color`/`Palette` change (§2.13) at
M1, leave the rest of the webengine code under `qtwebplot` until its Phase 5
rehome, bridged by the shim. **Status:** accepted (Theme early, webengine
late) — revisit at Phase 0.

---

## [D7] `RenderHandle.update()` rebuild — preserve interaction, avoid fl__icker

**Context.** Phase 1 `update()` = "full rebuild of inner primitives,
reusing the widget" (spec §2.8). Beyond range/selection ([D2]), a full
clear-and-readd can **flicker** and can thrash if `set_root` is called
rapidly (reactive previews, Phase 4).

**Options.** (a) clear+rebuild every time (simplest); (b) rebuild into an
offscreen layer then swap; (c) coalesce rapid updates (trailing-edge, reuse
the event throttle). 

**Recommendation.** (a) for Phase 1 correctness, plus the existing
throttle pattern reused to **coalesce** bursts at the `View.set_root` level
(not in the backend). Real diffing stays deferred (Q4 resolved → Phase 4).
**Blocks.** M3/M4. **Status:** low urgency; revisit if flicker shows.

---

## [D8] Event source identity for Overlays and axes-level events

**Context.** `Event.source_id: ElementId` assumes every event traces to one
Element. But a `RangeEvent` comes from a **shared ViewBox/Axes** in an
Overlay — it belongs to the *surface*, not a single child. Overlays/Layouts
have **no `id`** today (only Elements do).

**Options.**
- **A. Give Overlay/Layout ids too** (composition nodes become identifiable;
  range events carry the Overlay id). Con: widens the immutable-id story.
- **B. Axes-level events carry the `View`/handle id**, element-level events
  (pick/hover/tap on a specific series) carry the Element id. Two id spaces.
- **C. `source_id` becomes a small union** (`ElementId | AxesId`) with a
  `kind` discriminator.

**Recommendation.** **B** — least new surface: range/select(brush over the
whole axes) are surface events keyed by the handle; pick/hover/tap are
element events keyed by the clicked series' Element id. Document which
events are surface vs element in the §2.10 table. **Blocks.** M4.
**Status:** accepted (surface vs element ids) — apply the §2.10 note at M4.

---

## [D9] `Capabilities.max_recommended_points` — scalar vs context

**Context.** Auto-routing uses one scalar per backend. But the real
threshold depends on element type and options — pyqtgraph with
`useOpenGL=True` carries far more than without; a Curve scales differently
than a Scatter.

**Options.** (a) keep the scalar — coarse but simple and good enough for
"obvious" routing; (b) make it a callable `recommended_max(element) -> int`;
(c) per-element-type table in `Capabilities`.

**Recommendation.** **(a) for Phase 1** — auto is explicitly a convenience,
logged, overridable; a coarse scalar is fine. Revisit to **(b)** only if
real workloads mis-route. **Blocks.** M2 (informational). **Status:**
accept scalar, note the limitation.

---

## [D10] Negotiation memoization — build it or skip it?

**Context.** Spec §2.1/§3.2 mention caching negotiation on the root's
value-hash. Now that hashing is well-defined ([G] in §11), a cache is
*possible* — but negotiation is O(nodes) and cheap.

**Recommendation.** **Skip the cache in Phase 1** (premature; `set_root`
isn't hot enough to need it, and a stale cache across `set_backend_priority`
changes is a footgun). Keep `negotiate` pure and fast; add a bounded LRU
only if profiling says so. Remove the "may be memoized" language from spec
§3.2 to avoid implying a component that won't exist. **Status:**
recommend explicit *no cache* for now.

---

## [D11] CompositeRenderHandle.export — whole or per-pane?

**Context.** `export(fmt, path)` on a multi-pane composite is ambiguous:
one stitched image of the container, or one file per pane?

**Options.** (a) grab the whole container widget as one raster (works for
png; not svg/pdf); (b) per-pane export to `path`-derived names, returning a
list; (c) refuse `export` on composites in Phase 1.

**Recommendation.** **(c) for Phase 1** — `export` is a single-surface
operation; raise a clear "export individual panes via their own handles"
message on composites. Revisit stitched export if users ask. **Blocks.**
M5. **Status:** low urgency.

---

## [D12] Brush selection mechanism (pyqtgraph)

**Context.** pyqtgraph has no built-in "rubber-band drag → selected point
indices"; we must build the brush that produces `SelectEvent`. Needed for the
roadmap Phase 1 gate (linked brushing) at M4.

**Options.**
- **A. `ViewBox` RectMode + read rect on mouse-release.** No extra UI; on
  release, test each element's snapshot points against the bounds → indices.
  Con: collides with rect-zoom (ViewBox uses RectMode for zoom).
- **B. Toggleable draggable `RectROI` / `LinearRegionItem`.** Explicit brush
  affordance the user turns on; emits as it moves. Con: adds UI + a mode.
- **C. Modifier-drag** (e.g. Shift+drag = select, plain drag = pan/zoom).
  Familiar; no mode UI. Con: must intercept ViewBox mouse handling.

**Recommendation.** **C** (modifier-drag select) — no persistent UI, doesn't
fight zoom, matches common plotting tools. Compute indices per element from
its snapshot x/y against the dragged bounds. **Blocks.** M4.
**Status:** open — decide during M4 build.

---

## Index

| ID | Topic | Blocks | Status |
|----|-------|--------|--------|
| D1 | **Data layer (container-agnostic, lazy-first)** | M1 (contract) | ✅ resolved → spec §6 |
| D2 | ViewState in RenderHandle | M3/M5 | accepted — apply §2.8 at M3 |
| D3 | materialize pass (now load-bearing for D1) | M5 / Phase 5 | accepted — seam M5, async P4–5 |
| D4 | auto-Overlay supports-all fix | M2 | accepted — apply §3.3 at M2 |
| D5 | threading enforcement (entry-only) | M4 | accepted — revisit at M4 |
| D6 | qtwebplot→qtviz rehome (Theme early) | Phase 0 | accepted — revisit at Phase 0 |
| D7 | update() rebuild flicker/coalesce | M3/M4 | accepted — revisit if seen |
| D8 | event source identity (axes vs element) | M4 | accepted — apply §2.10 at M4 |
| D9 | capabilities scalar vs context | M2 | accepted (scalar) — revisit on mis-route |
| D10 | negotiation memoization (none) | M2 | accepted (no cache) |
| D11 | composite export semantics | M5 | accepted — revisit at M5 |
| D12 | brush selection mechanism (pyqtgraph) | M4 | open — decide during M4 |
