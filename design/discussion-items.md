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

**Resolution (per user).** Don't layer on pyqtgraph's defaults and manage
conflicts — **own the mouse model**. Implemented `QtvizViewBox(pg.ViewBox)`
(`backends/pyqtgraph/_interaction.py`): left-drag pan, wheel zoom, **Shift+
left-drag** rubber-band select → `SelectEvent`, left-click(empty) → `TapEvent`,
range → `RangeEvent`. Programmatic `select_bounds()` is the same path the
gesture calls (and the deterministic test hook). **Status:** ✅ resolved.

---

## [D13] Async materialize UX (data-core milestone)

**Context.** While a lazy ref materializes off the GUI thread, what does the
View show?

**Underlying.** A dask/zarr `materialize()` can take seconds. Qt's golden rule
(spec §2.14): the GUI thread must never block — if it does, the whole app
freezes (no repaint, no input) until compute finishes. So materialize runs on a
`qtviz.threading.Worker`, returns a `Future`, and the View re-renders when the
Future resolves *back on the GUI thread*. That single change makes rendering
**asynchronous**: today `View._build()` assumes a handle exists synchronously;
with lazy data the View becomes a small state machine — `empty → loading →
rendered`, plus `error`. Two hard parts ride along regardless of which option
we pick:

- **Re-entrancy.** Pan/zoom or rapid `set_root` can leave several
  materializations in flight at once. The View needs a monotonic `build_id`;
  when a Future resolves it's applied only if it's still the latest, else
  dropped. Without this, a slow early result can overwrite a fast newer one
  (last-writer-wins races, stale plots).
- **Errors.** `materialize()` can raise (bad query, missing file, OOM). The
  pipeline must surface that (error widget + log), not hang or crash the app.

The actual choice is only *what occupies the View's slot during `loading`*:

**Options.**
- **(a) placeholder/loading widget** — a blank/spinner `QWidget` swapped in
  while computing, swapped out for the render. Clean, but on every *update*
  (e.g. a reactive tick, a backend switch) the user sees content → placeholder →
  content: a flicker.
- **(b) keep the last render** — leave the previous plot up (optionally dimmed
  with a small busy indicator) until the new one is ready, then swap. No flicker,
  smooth "live" feel — but it shows **stale data** transiently (old viewport for
  a moment), and on the *first* render there is no "last" to keep, so it must
  fall back to (a).
- **(c) block** — rejected; it's the freeze we're avoiding.

**Recommendation.** **(b) when a prior render exists** (no flicker; matches how
good interactive tools keep old map tiles visible while new ones load), **(a) on
first render**, with a subtle busy affordance so "stale" never looks like
"hung." Errors → small error widget + logged. **Status:** ✅ applied — the View
keeps the last render visible during an async rebuild (placeholder only on
first render), a monotonic `build_id` drops stale results, and resolve runs on a
`ThreadPoolExecutor` (so a slow resolve doesn't stall others), delivered back to
the GUI thread via a queued signal. `core/view.py`; tested in `test_async.py`.

---

## [D14] Data binding — accessors, not column-name introspection  ⟂ REFRAMED

**The reframing (per user).** The previous framing — "enumerate each Element's
string column fields (`COLUMN_FIELDS`) so `narrow` can push projection down" —
baked in a narrow assumption: that a channel is *always* a named column. The
stronger model is **functional**: each channel maps to an **accessor** that is
*evaluated against the data object*. A column name is just the trivial accessor
`lambda d: d[name]`. So `Scatter(df, x="a", y="b")` is the easy special case of
`Scatter(df, x=lambda d: d["a"], y=lambda d: d["b"])`.

**Why this is actually *better* for out-of-core (the key insight).** Apply the
accessor to the **lazy** data object and the container's own engine does the
projection pushdown — better than `select(names)` could:
- `x="time"` → `ddf["time"]` → a lazy dask Series; computing it reads only that
  column (Parquet/Polars projection pushdown).
- `x=lambda d: d["a"] + d["b"]` → a lazy expression touching only `a`, `b`;
  dask's graph tracks the dependency, so materializing computes only those two —
  *and* shares subcomputation when channels are computed together.

So we do **not** need `Element.columns()` / `COLUMN_FIELDS` / `select(names)` at
all: the accessors *are* the projection, resolved by the container. The earlier
design was reinventing — worse — what dask/polars already do. **This dissolves
G4 / the original D14.**

**The accessor spectrum** (`str | Expression | Callable | ArrayLike`), ordered
from most-static to most-flexible:

| Accessor | Covers | Lazy-safe | Serializable | Static-checkable | Value-equal |
|----------|--------|-----------|--------------|------------------|-------------|
| `str` (name) | one column — sugar for `col(name)` | ✓ | ✓ | ✓ schema | ✓ |
| `Expression` (`col("a")+col("b")`) | derived / transforms / predicates | ✓ | ✓ | ✓ schema | ✓ |
| `Callable[[data], col]` | arbitrary Python | ✓ *if written lazily* | ✗ | ✗ | by identity |
| `ArrayLike` (literal) | pass-through values | ✓ | ✓ (it's data) | ✓ | by fingerprint |

**`Expression` is the sweet spot, and now first-class.** It is a qtviz-owned,
immutable AST with operator overloading — `qv.col("pop").log()`,
`qv.col("a") + qv.col("b")`, `(qv.col("x") >= 0) & (qv.col("y") < 10)` (the last
doubles as a `window` predicate). Because it's *our* data structure it keeps
every static property `str` has — **serializable** (round-trips to a Studio
project file via `to_dict`), **introspectable** (`expr.columns()` walks the AST
for `col` nodes → exact referenced columns → schema validation *and* explicit
pushdown), **value-equal** (immutable value), and **lazy** (`resolve(native)`
compiles to operations on the native object: arithmetic / comparison / boolean
via Python operator overloading work lazily on dask/polars and eagerly on
pandas/numpy; transforms dispatch through numpy ufuncs, or narwhals where it
broadens container/transform coverage). So:

- `str` ⊂ `Expression` (a bare name is the atom `col(name)`).
- `Expression` is `str` *generalized to derived columns while keeping all of
  str's nice properties* — the preferred way to express anything beyond a raw
  column.
- `Callable` is the **escape hatch** for genuinely arbitrary Python (custom
  funcs, branching) — at the cost of the three static properties below.
- `ArrayLike` covers "I already have the array, no data object."

narwhals (already a transitive dep) is the natural compile target to broaden
`Expression` transforms across pandas/polars/arrow/dask; the AST stays ours so
serialization/introspection don't depend on it.

**The costs are now confined to `Callable` only** — `Expression` gives derived
columns *without* paying them, which is exactly why it's first-class.
- **Validation.** Can't check a lambda against a schema without running it.
  → keep eager schema validation for `str` (early typo errors stay); defer
  callable/array validation to first resolve (clear error if it raises / lengths
  mismatch).
- **Serialization (Studio, spec §10).** A lambda can't round-trip to a project
  file. → `str` / `ArrayLike` persist; callables are *code-only*. The future
  `Expression` type is the serializable-derived path.
- **Identity / hashing (spec §2.1).** `lambda is not lambda`, so two Elements
  built from separate lambdas won't be value-equal. → the value-key uses
  *identity* for callables (a reused Element is still equal — so the negotiation
  cache and update short-circuit keep working for the common case) and
  value/fingerprint for str/array. Documented.
- **Laziness footgun.** A callable that forces eager (`np.asarray(d["a"])`)
  breaks pushdown. → document: write accessors in the container's lazy idiom.

**What it changes in the core.**
- `Accessor = str | Expression | Callable | ArrayLike` (str normalized to
  `col(str)` internally, so resolution has three paths: Expression, Callable,
  ArrayLike).
- `Element` exposes **`channels() -> dict[role, Accessor]`** (e.g. Scatter →
  `{"x": self.x, "y": self.y, "color": self.color_by, "size": self.size_by, …}`),
  replacing `COLUMN_FIELDS`. Roles are fixed names the renderer knows.
- `DataRef.resolve_channels(channels) -> dict[role, ndarray]` applies every
  accessor to the (lazy) native object and computes them **together** (one pass;
  the container pushes down). For lazy refs this runs on the Worker (D13).
- Renderers read channel arrays **by role** (`data.series("x")`), never seeing
  the accessor — a string, a lambda, and a raw array look identical to a
  renderer.
- `select(names)` is **dropped** (subsumed by resolution); `window` stays for
  viewport (D16); `data` becomes optional when all channels are `ArrayLike`.
- A post-resolve **length check** replaces the schema column check for non-str
  accessors (all role arrays must share length).

**Interactions.** This also softens [D17]: since renderers consume role-arrays
of known dimensionality, the tabular/gridded split matters mostly to the
*adapter* (how to `getitem`/compute), not the renderer. And it folds nicely into
[D13]: "resolve channels" is the unit the async Worker materializes.

**Decision (per user).** Adopt the full accessor spectrum
`str | Expression | Callable | ArrayLike` now — `Expression` is **first-class,
not deferred**. v1 `Expression` covers `col`, arithmetic, comparison/boolean
(derived columns + window predicates), literals, and a starter set of
numpy-ufunc transforms (`log`/`abs`/`clip`/…), with `to_dict`/`from_dict`
serialization and `columns()` introspection; narwhals broadens transforms/
containers later without changing the AST. `str` keeps eager schema-validation
(early typos); `Callable` validates at first resolve and stays code-only.
**Status:** ✅ accepted — see updated `milestone-data-core.md` §3/§8.

---

## [D15] Materialize safety guard

**Context.** Materializing an un-windowed huge lazy ref could exhaust memory.

**Underlying.** `materialize()` pulls the (narrowed) lazy data into RAM as
numpy. Narrowing by *columns* (D14) helps, but if no *row* window is applied a
1B-row frame is still 1B × (few columns) → tens of GB → OOM crash. And it's not
just unsafe, it's **pointless**: the native backends can't draw that many points
anyway — `Capabilities.max_recommended_points` is 2M for pyqtgraph, 100k for
matplotlib. Asking either to plot 1B raw points would be slow-to-impossible even
if the RAM existed. So "materialize a billion points to scatter them" is the
wrong operation on two counts.

The *right* operation at that scale is **aggregation, not materialization**:
Datashader rasterizes the lazy object into a screen-resolution image
(`native()` → dask → aggregate → `ImageItem`) without ever building a dense
point array. That's what `Scatter(scale="auto"|"datashader")` selects — but the
Datashader integration is Phase 4. This milestone has the *threshold* already
(`max_recommended_points`) but not the *aggregation path*. So the question is
what to do in the gap.

**Options.**
- **(a) hard `limit`** — `materialize(limit=N)` caps rows. Fine as an *explicit*
  preview ("show me the first 10k"), but a *silent* cap is misleading: the first
  N rows are not a representative sample, so the plot would lie.
- **(b) auto-route to a scale strategy** — when `size > max_recommended_points`,
  aggregate via Datashader instead of materializing raw. The correct big-data
  answer, but it *is* Phase 4.
- **(c) warn-and-proceed** — log a WARNING ("materializing 1B points; backend
  recommends ≤2M — consider a window or `scale='datashader'`") and compute
  anyway, trusting the user has RAM or intent.

**Recommendation.** This milestone: **(c)** + support explicit `materialize
(limit=)` for previews; **(b)** lands in Phase 4 on top of this core. This honors
the "no silent caps" principle — we don't quietly truncate (which would
misrepresent the data) and we don't quietly risk OOM (we warn loudly at the
known threshold), but we also don't *block* a user who knows what they're doing.
**Status:** ✅ accepted (per user) — warn at `max_recommended_points` +
`materialize(limit=)` for previews; auto-route to Datashader is Phase 4.

---

## [D16] Viewport→window auto-trigger is deferred

**Context.** `window` is built here as a lazy-safe primitive; wiring zoom →
re-window → re-materialize (viewport-driven re-aggregation) is the Phase-4
reactive/Datashader piece.

**Underlying.** Big-data plots don't show all the data — they show the *visible
viewport* at the current zoom. As the user pans/zooms, the data is re-windowed
to the new bounds, re-aggregated, and re-rendered, so the picture is always a
fresh aggregate of what's on screen (this is how Datashader/holoviews
`datashade` behaves — the image sharpens as you zoom in). The loop is:

```
RangeEvent (zoom) → new bounds → ref.window(x=(lo,hi), y=(lo,hi))
                  → re-materialize / re-aggregate (Worker) → re-render
                  ▲ debounced (trailing-edge, like event throttling) so a
                    drag doesn't fire a recompute per pixel
```

Standing this up needs four things: the `window` primitive (built here), the
async materialize pipeline (built here), Datashader aggregation (Phase 4), and a
debounced, re-entrant `View ↔ RangeEvent ↔ re-window` feedback loop (Phase 4).
Building the loop *now* would mean wiring debounce + range feedback + Datashader
all at once — a much larger, riskier unit, and Datashader carries its own
integration risk (round-trip latency, flagged in the roadmap). The clean seam is
to ship the **primitives** now (with `window` proven by direct/programmatic
tests in the conformance suite) and let Phase 4 wire the **loop** on top.

**Recommendation.** Ship `window` as a primitive now; defer the auto-trigger.
**Status:** ✅ accepted (per user) — `window` is a lazy-safe primitive; the
zoom→re-window→re-aggregate loop is Phase 4.

---

## [D17] Shape is chosen by the adapter (no ref bridging)

**Context.** Residual from D1: can a 1-D gridded ref serve a tabular Element?

**Underlying.** The data layer has two access shapes with *different* renderer
APIs: **tabular** (named columns, row-oriented — `TabularRef.series(name)`;
DataFrame/Arrow/dict) and **gridded** (an N-D lattice with coordinates —
`GriddedRef.grid()`; ndarray/xarray/zarr). They're deliberately non-overlapping,
which keeps the protocol small and Element validation a one-line `isinstance`
check (Scatter needs tabular, Image needs gridded).

The wrinkle: some containers are genuinely **either**. A 1-D xarray `DataArray`
(say temperature over time) is *structurally* gridded — one dim, coord = time,
values = temp — but the common *intent* is to `Curve`/`Scatter` it as
`x=time, y=temp`, i.e. **tabular** access. A 2-D `DataArray` is gridded (an
image). So the same library produces objects that should present as different
shapes depending on dimensionality/intent. Where does that get resolved?

- **Ref-level bridging** — give `GriddedRef` an `as_tabular()` that 1-D grids
  implement, and let Element validation accept a gridded ref and bridge it.
  Cost: every gridded ref carries bridging logic, Element validation grows a
  special case, and the clean "two disjoint shapes" property erodes.
- **Adapter picks the shape (recommended)** — the *xarray adapter* inspects the
  object: 1-D `DataArray` → `TabularRef` (dim and values exposed as columns),
  2-D+ → `GriddedRef`. The shape decision lives in *one place per container* (the
  adapter, which already understands that container), the `DataRef` protocol
  stays minimal, and Elements need no changes — a Scatter on a 1-D `DataArray`
  "just works" because the adapter handed it a tabular ref. Same principle that
  makes the registry clean: container knowledge belongs in the adapter.

**Cost of the recommended path:** for a truly ambiguous object the adapter must
pick a default that might not match intent (a 2-column structured array → tabular;
a 1-D array → the adapter's choice). Mitigation: ship explicit shape-forcing
escape hatches — `qv.tabular({...})` / `qv.gridded(arr)` — so a user can override
the default when needed. These are escape hatches, not the common path.

**Recommendation.** Adapter picks the shape (1-D → tabular, N-D → gridded;
structured ndarray → tabular, plain → gridded), with `tabular()`/`gridded()`
overrides for ambiguous cases. No ref-level bridging, no Element changes.
**Status:** ✅ accepted (per user) — shape is the adapter's call; ship the
`qv.tabular()` / `qv.gridded()` escape hatches with the lazy/gridded adapters.

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
| D8 | event source identity (axes vs element) | M4 | ✅ applied → spec §2.10 |
| D9 | capabilities scalar vs context | M2 | accepted (scalar) — revisit on mis-route |
| D10 | negotiation memoization (none) | M2 | accepted (no cache) |
| D11 | composite export semantics | M5 | ✅ applied — composite.export raises (export panes individually) |
| D12 | brush selection mechanism (pyqtgraph) | M4 | ✅ resolved → custom QtvizViewBox (Shift-drag) |
| D13 | async materialize UX (placeholder vs keep-last) | data-core | ✅ applied — keep-last + placeholder, build-id stale-drop, error widget |
| D14 | **data binding: accessors `str\|Expression\|Callable\|ArrayLike`** | data-core | ✅ accepted (Expression first-class) |
| D15 | materialize safety guard (huge un-windowed lazy) | data-core | ✅ accepted — warn + `limit=`; Datashader P4 |
| D16 | viewport→window auto-trigger deferral | data-core / P4 | ✅ accepted — `window` primitive now, loop P4 |
| D17 | shape chosen by adapter (no ref bridging) | data-core | ✅ accepted — adapter picks shape + `tabular()`/`gridded()` |
| D18 | datashader: backend-agnostic pipeline transform | Phase 4 | ✅ Scatter→Image in resolve_node (see milestone-phase4) |
| D19 | datashader auto-route policy | Phase 4 | ✅ `set_raster_threshold`; lazy/unknown size routes |
| D20 | raster output: RGBA shade vs aggregate+theme cmap | Phase 4 | ✅ RGBA shade now; aggregate+theme cmap future |
| D21 | dynamic viewport re-aggregation seam | Phase 4b | ✅ RasterController + RasterTarget (pyqtgraph + matplotlib) |
| D22 | datashader coverage (lines, categorical color) | Phase 4 | ✅ points + lines + value/categorical agg; deeper gaps → `capabilities-gaps.md` |
