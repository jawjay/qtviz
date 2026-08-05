# qtviz — the decision log ([D1]–[D60])

> **This is the project's decision log** — every `[Dnn]` tag in code,
> commits, and tests resolves to an entry here or in the arc document that
> introduced it (later decisions live with their arc: [D121]–[D136] in
> `2.0-mark-ir-and-surface.md`, [D137]–[D144] in `public-release.md`; the
> Index below maps the rest).
>
> Entries were written *while deciding*, in the working format —
> **Context** (why it exists) · **Options** · **Recommendation** ·
> **Blocks** (which milestone) · **Status** — and are preserved as the
> record. Statuses are point-in-time; the shipped state is what the code,
> tests, and CHANGELOG say. Entries are never renumbered or deleted.

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

## [D24] Webengine default Element renderer — Plotly

**Context.** The webengine backend turns native Elements into a *web* figure to
host in a `QWebEngineView`. The legacy package has two figure libraries wired —
Plotly and Bokeh (HoloViews delegates to Bokeh). Which one is the Element→figure
renderer path?

**Underlying.** Reading the code, the Plotly path is already the complete one:
`ext/plotly/_runtime.py` wires `plotly_hover/click/selected/relayout` through the
bridge; `ext/plotly/backend.py` exposes the mutation verbs (`react`/`restyle`/
`relayout`/`extend_traces`/`resize`) and a `Theme`→template translator
(`_plotly_template_from`). Plotly also gives WebGL (`scattergl`), 3D, native
box/lasso select, and static export via kaleido — all the capabilities the
webengine record needs to declare. Bokeh's value is as a *host* for arbitrary
existing figures (and the HoloViews→Bokeh path), not as a second Element renderer.

**Recommendation.** Plotly is the one Element→figure renderer path. Bokeh stays
available only as a `RawFigure` host (see [[D26]]). Two element-renderer paths
would double the surface for no near-term gain.
**Status:** ✅ resolved (per user) — Plotly is the default/only Element renderer;
Bokeh is a passthrough host. Drives W1/W2 of `webengine-rehome.md` §8.

---

## [D25] Webengine async render contract — handle now, drain on ready

**Context.** qtviz `Backend.render()` is synchronous: the handle is ready on
return. A `QWebEngineView` is not — HTML loads, the QWebChannel handshake fires,
*then* the page is live. How does the async backend satisfy a synchronous contract
without changing `View`?

**Underlying.** It already fits. `WebBridgeView.send()` buffers into a
`deque(maxlen=128)` until `_is_ready`, and `_on_ready()` drains it before emitting
`ready`. So `render()` can return a `WebEngineRenderHandle` immediately; any
`restore_state`/theme/data issued before `ready` is queued and replayed; events
start flowing after `ready`. No `View` change, no new async path (contrast the
*data* async path keyed on `node_is_lazy` — this is *backend* async, self-contained
in the handle). The soft part is UX: Chromium's first paint is visibly slow, so a
blank pane looks broken. The data layer already solved the analogous problem with a
placeholder + keep-last ([[D13]]); reuse that pattern for a "loading" placeholder
until `ready`.

**Recommendation.** Return the handle immediately and lean on the existing command
queue + `ready` signal — no `View` change. Show a loading placeholder until `ready`.
**Status:** ◑ accepted-pending-revisit (per user) — the handle-now + command-queue
contract is **firm**; the *loading-placeholder* nicety is flagged to revisit once we
see real page-load latency (might be unnecessary, or might need keep-last on rebuild).

---

## [D26] Raw-figure passthrough — a first-class `RawFigure` element

**Context.** A user has an existing Plotly/Bokeh/HoloViews figure (or
`from_holoviews` hits an element qtviz doesn't model natively) and wants it hosted.
Does that figure enter qtviz as an Element, or through a backend-only side door?

**Underlying.**
- **Backend escape hatch** — `WebEngineBackend.render()` accepts a bare figure
  object, no Element. Simpler, no negotiation special-case. But it isn't
  composable: a raw figure can't sit in a `Layout` beside a native pane, can't
  overlay, and `from_holoviews` has no *uniform* value to return for the long tail.
- **First-class `RawFigure(figure)` element (chosen)** — a real Element whose only
  `supports()` backend is webengine. Negotiation already keys off per-element
  `supports()` (`backends/__init__` + the negotiator), so "exactly one backend
  supports this element" falls out with no special case; asking pyqtgraph/mpl to
  render it raises the normal unsupported-element error. It composes in
  `Layout`/mixed-backend panes and gives `from_holoviews` ([[D28]]) a single uniform
  fallback return.

**Recommendation.** First-class `RawFigure` element that negotiates only to
webengine; Bokeh/HoloViews objects are hosted through it ([[D24]]).
**Status:** ✅ resolved (per user) — build `RawFigure` as an Element in W3;
`from_holoviews` returns it for unsupported elements.

---

## [D27] Webengine event/selection fidelity mapping

**Context.** The public event stream must be qtviz typed events, so a webengine
pane is indistinguishable to `View.on(...)`. The legacy per-library event
dataclasses become an internal detail; what's the precise library→typed-event map?

**Underlying.** Mostly mechanical, given `ext/plotly/_runtime.py`'s payloads:
`plotly.click`→`PickEvent(point_index, x, y)`; `plotly.hover`→`HoverEvent`;
`plotly.unhover`→`HoverEvent(point_index=None)`; `plotly.relayout`→`RangeEvent`
(parse `xaxis.range[0/1]`/`yaxis.range`); `plotly.selection`→`SelectEvent(indices,
bounds)`. **The one real subtlety:** Plotly identifies a point as `(trace_index,
point_index)` *per trace*, but `SelectEvent.indices` is a flat list of source-row
indices. For a single-Element single-trace figure `point_index == row index`
trivially. For an `Overlay` (many traces), the handle must hold a
**trace→(source_id, row-offset) table** and translate so each `SelectEvent` carries
the right `source_id` and that Element's row indices.

**Recommendation.** Lock the per-event map above; implement the single-trace case in
W1/W2 and the trace→element table when Overlay selection is wired (W2/W3).

**Resolution (W3, per user).** Multi-trace routing **adopts native semantics**: the
native pyqtgraph backend emits **one `SelectEvent` per selectable element** (each
with that element's in-bounds row indices — `pyqtgraph/_interaction.py`
`select_bounds`). Webengine matches it: group a `plotly.selection`'s points by
`trace_index` → `source_id` (the table `_figure.build` already returns) and emit one
`SelectEvent` per source element. The W1 flattened surface-level select is replaced.
A `RawFigure` ([[D31]]) has no sub-elements, so its selection emits a single
`SelectEvent` under the figure's own id. Click/hover already carry the right
`source_id` via the same table. The simpler "single flat surface select" is dropped
because it loses the per-element identity that linked brushing needs.
**Status:** ✅ resolved (per user) — per-element `SelectEvent` routing (matches
native); lands in **W3a**. row-offset isn't needed (point_index is the row index per
trace, so the table is trace→source_id).

---

## [D31] `RawFigure` passthrough — design

**Context.** D26 resolved that an existing Plotly/Bokeh/HoloViews figure enters
qtviz as a first-class `RawFigure` element negotiating only to webengine. W3 builds
it; this records the design specifics.

**Underlying.**
- **Library detection.** `RawFigure(figure, kind=None)` auto-detects the library by
  object type (plotly `Figure` / bokeh model / hv element), with an explicit `kind=`
  override for ambiguous inputs.
- **Hosting.** `WebEngineBackend.render()` branches: a `RawFigure` routes to the
  matching legacy host (`PlotlyBackend` / `BokehBackend` / `HoloViewsBackend`) and
  skips `_figure.build`. The legacy `HoloViewsBackend` already renders any hv object
  via Bokeh, so "raw HoloViews renders" is nearly free.
- **Composability.** A `RawFigure` is a *whole figure* — it can't overlay with native
  traces (the webengine path builds one Plotly figure from traces; a raw figure can't
  merge in). So it's **standalone**: rejected inside an `Overlay`; allowed as a
  `Layout` pane in W4 (the LayoutHost hosts each pane's own `WebBridgeView`).

**Recommendation.** Auto-detect host + `kind=` override; render-branch in the
backend; standalone (non-composable) element.
**Status:** ✅ resolved (per user) — build in W3a; standalone; auto-detect with
override. Events for a Plotly raw figure use the Plotly map (W3a); Bokeh/hv raw
figures render in W3a but get typed events in **W3b** ([[D32]]).

---

## [D32] W3 event-translation split — Plotly now (W3a), Bokeh later (W3b)

**Context.** The W3 gate says "raw HoloViews → brush emits typed events." hv renders
through Bokeh, so meeting it literally needs a **Bokeh** event-translation map
(`bokeh.tap`→Pick, `bokeh.selection`→Select, `bokeh.ranges_update`→Range) on top of
the Plotly one — roughly doubling the translation surface.

**Underlying.** Splitting keeps increments verifiable and value-first:
- **W3a:** `RawFigure` passthrough for all three libraries (they all *render*) +
  Plotly typed events + per-element selection routing ([[D27]]) + Plotly
  brush→`SelectEvent`. hv/bokeh raw figures render but emit Plotly-only events (i.e.
  none for the bokeh-hosted ones yet).
- **W3b:** the Bokeh event-translation map, so hv/bokeh `RawFigure`s also emit typed
  events — fully meeting the W3 gate.

**Recommendation.** Split W3a/W3b as above.
**Status:** ✅ resolved (per user) — W3a now, W3b after. W3a does not fully meet the
literal "hv brush emits events" gate (that's W3b); W3a's gate is "all 3 libs render +
Plotly raw figure + native Overlay emit per-element typed events."

---

## [D33] Webengine W5 transport — base64 now, custom URL-scheme handler for scale

**Context.** W5 ships large figure data to the embedded browser as **binary**
instead of JSON ([[D29]]). How does the binary blob cross the bridge? Full analysis
in `webengine-arrow-transport.md`.

**Underlying.** Today data crosses as JSON text (embedded in the HTML, and as a JSON
literal inside a `runJavaScript` source string) — the size/CPU/precision ceiling on
the data-intensive path. Options: **(A)** base64 over the existing channel — zero
new infra but a text step and a heavy `runJavaScript` string, good to a few MB;
**(B)** a custom `qtviz://` URL-scheme handler (`QWebEngineUrlSchemeHandler`) — true
binary `fetch`, no base64, no open port, scales to 100 MB, but the scheme must be
registered before the QApplication and needs a buffer registry; **(C)** local HTTP —
true binary but opens a TCP port (strictly worse than B here); **(D)** QWebChannel
`QByteArray` — still base64.

**Recommendation.** Phased: **W5.1 base64 (A)** to prove the JS-side
Arrow→typed-array→Plotly pipeline with minimal infra; **W5.2 custom scheme handler
(B)** to hit <100 ms / 100 MB — only the data-blob transport changes. C is the
fallback if scheme registration proves impractical.
**Status:** ✅ resolved (per user) — base64 (W5.1) → scheme handler (W5.2); benchmark
first ([[D29]]).

---

## [D34] Webengine W5 binary format — raw typed-array buffers (revised)

**Context.** What binary encoding for the bulk data columns?

**Underlying.** **Arrow IPC** (columnar; dtypes/nulls/strings/multi-column; zero-copy)
vs **raw `Float64Array` buffers + a tiny JSON manifest** (minimal, no JS dep). The
doc first picked Arrow IPC for future-proofing.

**Revision (per user, alongside [[D37]]).** Implementation made the payload concrete:
the binary transport **only ever carries numeric arrays** (`x`/`y`/`z`/errors);
everything categorical/string stays small JSON. So Arrow's value (strings/nulls/
multi-dtype) never applies here, while its cost — an **`apache-arrow` JS dependency**
— **conflicts with the 100% offline requirement** ([[D37]]): another lib to bundle, or
a CDN we've banned. Raw buffers need **no JS library** (`new Float64Array(buf)` is
built in).
**Status:** ✅ resolved (per user) — **raw typed-array buffers**, not Arrow IPC. The
data layer stays Arrow-aware internally; Arrow over the wire only if a future payload
needs strings/nulls.

---

## [D35] Webengine W5 figure-splitting + Plotly typed-array API

**Context.** Binary transport requires splitting the figure into structure (small
JSON) + bulk data (binary), with a JS reassembly step that feeds typed arrays to
Plotly.

**Underlying.** `_figure.build` must emit a *data-by-reference* figure
(`{column_id, dtype, len}` instead of inline lists); a JS handler decodes the Arrow
blob into typed arrays and injects them before `Plotly.react`/`newPlot`. Plotly.js
accepts typed arrays / its `{dtype, bdata}` typed-array spec — **but the exact
ingestion API + minimum Plotly version must be confirmed by a spike** before building.

**Cheap-win first.** `_figure.build` currently `.tolist()`s its arrays, handing
Plotly *lists* and defeating Plotly's own base64 typed-array encoder (numpy-only).
Step zero is a spike: keep numpy arrays and measure whether `to_json` already emits
base64 `{dtype, bdata}` — that may capture most of the win with no new transport
(W5.1a), leaving the explicit base64/Arrow split (W5.1b) only for the tail.

**Status:** open — spike (1) numpy-vs-lists base64 shortcut and (2) Plotly's
typed-array ingestion API/version; then design the `_figure` split if still needed.

---

## [D36] Webengine W5 custom-scheme registration timing

**Context.** A custom `QWebEngineUrlScheme` must be **registered before the
QApplication** is created — but qtviz shouldn't impose WebEngine setup on apps that
never use the webengine backend.

**Underlying.** Where does registration happen — at webengine-package import (too
eager; already a flake source), at first webengine render (too late — app exists), or
via an explicit one-time `qtviz.backends.webengine` init the app calls before its
QApplication? Affects packaging and the app-integration story.

**Status:** open — decide at W5.2 (only the scheme-handler transport needs it; base64
W5.1 does not).

---

## [D37] qtviz runs 100% offline — no CDN, ever

**Context.** The webengine backend embeds a browser, and the legacy bridge loaded the
plotting JS (plotly.js / bokeh.js) from a **CDN** (`plotlyjs="cdn"`,
`resources="cdn"`). A user flagged: a desktop plotting library must not need the
internet to draw a chart (air-gapped / firewalled / on a plane).

**Underlying.** Review confirmed the *only* network dependency is the JS *renderer*
libraries via CDN — **data is always local** (Python → embedded page; `setHtml` /
`runJavaScript` / `QWebChannel` / `qtviz://`), and the bridge JS (`qwebchannel.js`)
already loads from Qt's bundled resource. The fix is to bundle the renderer JS, which
**ships inside the installed `plotly` / `bokeh` Python packages** (`include_plotlyjs=
True`, Bokeh `INLINE`) — no download needed. This is promoted to a **hard
non-functional requirement** in `spec.md` §0.1, and it settles [[D34]] (no
apache-arrow over the wire).

**Recommendation.** Offline is mandatory. Inline the JS now (headless-verifiable: the
rendered HTML must contain no external `http(s)://`); in W5.2 the `qtviz://` scheme
serves the bundled plotly.js *and* the raw data buffers, removing per-page JS bloat.
**Status:** ✅ accepted (per user) — 100% offline is a hard requirement; bundle JS
locally, never a CDN. Conformance asserted headlessly on the generated HTML.

---

## [D38] Reactivity binds at the View root, not inside Elements

**Context.** Reactive `Signal` binding (roadmap Phase 4): state changes → the plot
re-renders, incl. linked brushing / crossfilter. Where does a `Signal` attach?

**Underlying.** Two models:
- **Signal inside the Element** (`Scatter(data=signal(df))`, the roadmap's phrasing).
  Ergonomic for "just swap the data", but **breaks the Element invariant** (spec §2.1:
  immutable, value-hashed, **Qt-free**) — a `Signal` is a `QObject`, pulling Qt into
  the pure data model and muddying value identity; and only the *bound field* is
  reactive (not tree structure / backend / theme).
- **Signal at the View root (chosen).** `View(derived(lambda: Scatter(filter(sel.get()),
  …)))` — Elements are built *fresh inside a `derived`* that reads signals and
  auto-tracks; the reactive graph lives *outside* the data model. Elements stay pure,
  the **whole node tree** is reactive (data, structure, backend, theme), and crossfilter
  falls out of `Signal + derived + View.on` with no special machinery.

**Recommendation.** View-root reactivity (`View` accepts a `Signal[Node]`). The
`Scatter(data=signal)` ergonomic can come later as **sugar that desugars to a
derived** — never as Qt-in-the-Element.
**Status:** ✅ accepted (per user) — Option B; Elements stay pure; `View(Signal[Node])`.
Common-case sugar deferred. Follows [[feedback-abstractions]] (general form, sugar later).

---

## [D39] Reactive runtime — auto-tracking, synchronous, simple propagation

**Context.** How do `derived` / `effect` know their dependencies and when to recompute?

**Underlying.** **Auto-tracking** (S-style): a global "current observer" stack; a
`Signal.get()` during a computation registers that computation as a subscriber — so
`derived(f)`/`effect(f)` track reads automatically (the sketch's intent). Kept
**synchronous, no async**. Propagation is **simple** (a `.set` notifies subscribers,
which recompute) plus a **`batch()`** to coalesce multiple `.set`s into one pass —
**not** full topological / glitch-free scheduling (which is what blows past the
~500-LOC budget). Honest cost: in a deep `derived` graph a node may recompute more
than once per update; acceptable for plotting-state graphs (shallow), revisit if a
real glitch shows.

**Recommendation.** Auto-tracking + synchronous + simple propagation + `batch()`;
defer topological ordering.
**Status:** ✅ accepted (per user).

---

## [D40] Reactive render, threading & lifecycle

**Context.** What happens on a signal change, on which thread, and how is it disposed?

**Underlying.**
- **Render:** a root-signal change schedules **one debounced full View rebuild** on the
  next Qt tick — reuse `View._rebuild` (keeps the last render visible; async for lazy
  data) + the trailing-edge throttle from `event.py`. Targeted per-element updates are a
  later optimization, not v1.
- **Threading:** `Signal.set` off the GUI thread marshals onto it via the existing
  `run_on_gui` (`core/threading.py`); the reactive graph runs **GUI-thread-only**, so
  no locks.
- **Lifecycle:** `Signal.subscribe` / `effect` return a `Disposable`; the `View` owns
  and disposes its root-signal subscription on teardown; optional `owner=<QObject>` for
  auto-dispose tied to a Qt object's destruction.

**Recommendation.** Debounced full rebuild; `run_on_gui` for cross-thread `.set`;
`Disposable` + View-owned subscription + optional `owner=`.
**Status:** ✅ accepted (per user).

---

## [D28] `from_holoviews` fallback to webengine

**Context.** The native HoloViews adapter (Phase 3) translates the common hv
elements to native qtviz Elements; the long tail (Sankey, Chord, custom hv) has no
native form. Where does it land?

**Underlying.** Depends on [[D26]], now resolved: the adapter translates what it can
natively (pyqtgraph/mpl — fast, interactive) and **falls back to a `RawFigure`** for
the rest, hosted full-fidelity on webengine via the legacy `HoloViewsBackend`
(`hv.renderer("bokeh").get_plot(obj).state`). That fallback target now exists by
decision, so the adapter can ship incrementally: common elements native, everything
else still renders.

**Recommendation.** `from_holoviews` returns native Elements where it can, else
`RawFigure(<hv state>)` on webengine.
**Status:** ◑ accepted-pending-revisit (per user) — principle accepted; the detailed
wiring (which elements native vs fallback, how `DynamicMap`/`Stream` map) is decided
in **Phase 3** when the adapter is built, not now.

---

## [D41] Spike-P2 — HoloViews adapter feasibility (the Phase 3 gate)

**Context.** Roadmap §0 / dev-plan §8 make Phase 3 (`from_holoviews`) the one
remaining major item gated on a feasibility spike. The risk (roadmap §6 #3): if
translation needs HoloViews *internals* that drift every release, the adapter is a
maintenance sink and we cut it (ship native-only).

**What was run.** A throwaway prototype (`from_holoviews`) walked an hv tree and
translated leaves + containers to qtviz Nodes, rendered headlessly via
`render_root(..., view_backend="pyqtgraph")`. HoloViews 1.22.1.

**Result — GO.** 10/10 cases rendered to a `GraphicsLayoutWidget`: Scatter, Points,
Curve, Bars, HeatMap, ErrorBars, Image, Overlay (`*`), Layout (`+`), and a nested
`(Scatter*Curve)+Bars`. Translation rode entirely on **stable public API** —
`.dframe()`, `.kdims`/`.vdims` (`.name`), `.dimension_values(2, flat=False)` +
`.bounds.lbrt()` for gridded Image, and plain iteration for Overlay/Layout. **Zero
internals touched.** Brittleness risk is low; the adapter does not bind us to hv's
private surface.

**Findings to carry into Phase 3 (deferred — not applied now):**
- Map dimensions **by role per element type**, not blind position: hv auto-promotes
  undeclared DataFrame columns to vdims, so e.g. `Points` must take x/y from both
  kdims while `Scatter` takes y from the first vdim.
- **Semantic-shape mismatches** (not blockers): hv `Histogram` is *pre-binned*
  (kdim=bin centers, vdim=Frequency) but qtviz `Histogram` bins a raw column → map
  hv `Histogram` onto qtviz `Bars`, or add a pre-binned mode. hv `Spread` is
  `y ± delta` (vdims `[y, spread]`) vs qtviz `Spread(y_lo, y_hi)` → translate via a
  derived accessor (`y-spread`, `y+spread`).
- Long-tail elements (Sankey/Chord/etc.) route to `RawFigure` on webengine per
  [[D28]]; `DynamicMap`/`Stream` map to `Signal`/typed events per spec §8.

**Status:** ✅ resolved — Spike-P2 passes; Phase 3 is feasible and unblocked. The
prototype is throwaway; the production adapter is built spec-first in Phase 3 (its
own milestone doc → benchmark suite → implement), folding in the findings above.

---

## [D42] HoloViews `Histogram`/`Spread` shape handling

**Context.** Two hv elements don't share qtviz's data shape (surfaced by [D41]).
hv `Histogram` is **pre-binned** (kdim=bin center, vdim=Frequency) but qtviz
`Histogram` bins a *raw* column. hv `Spread` carries `y ± Δ` (vdims `[y, spread]`)
but qtviz `Spread` takes explicit `y_lo`/`y_hi`.

**Recommendation.** Map hv `Histogram` → qtviz **`Bars`** (already-binned bars), and
hv `Spread` → qtviz **`Spread`** via Expression arithmetic (`y_lo=col(y)-col(Δ)`,
`y_hi=col(y)+col(Δ)`). No qtviz API change; the adapter absorbs the impedance.
Alternative considered: add a "pre-binned" mode to qtviz `Histogram` — rejected for
0.1 as scope the adapter doesn't justify.

**Status:** ✅ accepted (per user) — `Histogram`→`Bars`, `Spread`→`Spread` via
Expression `y±Δ`; no qtviz API change.

---

## [D43] `hvplot` integration mechanism

**Context.** The `hvplot` win (`native-pivot-research.md` §2e) is a pandas/xarray
one-liner that returns a Qt-native widget. Two ways to wire it.

**Options.** (a) Register `qtviz` as an **hvplot/HoloViews backend** so
`df.hvplot(kind="scatter", backend="qtviz")` flows through hvplot's machinery; or
(b) ship a thin **`.qtviz` DataFrame/Series accessor** (`df.qtviz.scatter(x, y)`)
that builds Elements directly, sidestepping hvplot internals.

**Recommendation.** Decide when stage 3b starts; lean toward whichever rides the
most-public surface (consistent with [D41]'s public-API-only principle). Detailed
path analysis (3 paths incl. "hvplot-as-builder" + effort) in
`phase3b-decisions.md` §1.

**Decision (3b).** **Path A — hvplot-as-builder.** hvplot's *output* is a HoloViews
object, which `from_holoviews` already translates; so we add only a thin convenience
`qv.from_hvplot(data, kind=..., **kw)` (== `from_holoviews(data.hvplot(kind=kind,
**kw))`, hvplot imported lazily) and document that wrapping hvplot output also works.
This rides hvplot's stable public contract (its return value), keeps coupling low
([D41]), and inherits `DynamicMap` support from [D44] L1 (hvplot emits a `DynamicMap`
for `groupby`/widgets/`datashade`). `hvplot` ships as an **optional extra**
`[hvplot]`; `import qtviz` never imports it. Path B (a native `.qtviz` accessor) is a
**deferred follow-up** — nice as an hvplot-free entry point but a second API surface
to own. Path C (a HoloViews plotting backend) is **rejected** — it re-opens the
already-rejected "Option A" (binds us to hv's plot-class internals;
`native-pivot-research.md` §2c).

**Status:** ✅ decided (3b) — Path A (thin `from_hvplot` + docs); B deferred; C rejected.

---

## [D44] `DynamicMap` / stream scope for 0.1

**Context.** hv `DynamicMap` + streams (`RangeXY`/`BoundsXY`/`Tap`/`Selection1D`)
are interactive. Full fidelity is bidirectional: qtviz events write back to the hv
stream's `.event(...)` so hv-side callbacks fire.

**Recommendation.** For 0.1, support **one-way** re-render (kdim widgets / param
changes → recompute node → `Signal[Node]` → debounced rebuild, [D38]); **defer**
bidirectional stream write-back (`Selection1D`/`RangeXY` → hv) to a follow-up.
Levels (L0/L1/L2), effort, and the read-vs-write breakdown in
`phase3b-decisions.md` §2.

**Decision (3b).** **Level 1 — one-way re-render** for 0.1; **defer Level 2**
(bidirectional stream write-back) to a follow-up once native event semantics settle.
Mechanism leans on the reactive substrate already built: `from_holoviews(dm)` returns
a **`Signal[Node]`** (the View already accepts a `Signal[Node]` root, `core/view.py`
`_is_reactive`), implemented as one writable `Signal` per kdim feeding a `derived`
that resolves `dm[values]` and runs the **static** translation on each frame.
**kdim exposure is composable, not a baked-in UI** (favoring general abstractions):
a sibling `from_holoviews_dmap(dm)` returns `(node_signal, {kdim: Signal})` so the app
drives kdims however it likes; a turnkey Qt kdim panel is shipped only as an
**optional example/helper**, not core. **Stream-only `DynamicMap`** (no kdims, can't
be widget-driven) degrades to **warn-and-static** — resolve + translate the current
frame natively and emit a warning that stream interactivity needs L2; the webengine
`RawFigure` path ([D28]) is the documented full-fidelity escape hatch.

**Status:** ✅ decided (3b) — L1 one-way (DynamicMap→Signal[Node], kdims as Signals,
optional widget-panel example); L2 deferred; stream-only → warn-and-static.

---

## [D45] HoloViews import destabilizes the offscreen-Qt test teardown

**Context.** Discovered while writing the Phase-3 spec-first suite: importing
`holoviews` (it pulls in numba/llvmlite + bokeh) at pytest **collection** time
crashes the whole offscreen suite at *interpreter teardown* (native fault in the
runpy/atexit path — numba/Qt teardown ordering). Same family as the "de-flake
suite (lazy WebEngine)" fragility.

**Mitigations.** (1) Spec-first modules order the adapter-absent `importorskip`
*before* the holoviews import, so collection never imports holoviews while the
adapter is unbuilt (done — keeps the default suite green now). (2) When the adapter
is implemented, import holoviews **lazily inside `from_holoviews`**, not at the
`qtviz.adapter.holoviews` module top, so importing the adapter (and hence
collecting its tests) stays cheap and safe. (3) If the full-run teardown still
faults once tests activate, isolate the holoviews render tests (separate process /
`-p no:cacheprovider` subrun in CI).

**Status:** ◑ mitigated — (1) + (2) applied in stage 3a (`from_holoviews` imports
holoviews lazily; `import qtviz` does **not** pull in holoviews). With the adapter
implemented and its tests active (holoviews imported at collection), the full
offscreen suite ran green **3× consecutively** — the earlier teardown fault did not
reproduce. Keep (3) (process isolation) in reserve and watch CI on Linux/Windows,
where numba/Qt teardown ordering may differ.

---

## [D46] Raster reverse-lookup — hover/inspect value on a datashaded view

**Context.** A datashaded `Scatter`/`Curve` renders as a bare RGBA `Image`; hover/pick
resolve through points, so a raster (no per-point identity) can't be inspected. The
datashader path already computes a per-pixel aggregate (`count`/`mean`) but discards
it — only `(rgba, bounds)` is returned. Reverse-lookup retains that aggregate and maps
a cursor coord → pixel → value. First step toward selection/brushing on rasters.

**Decisions (recommended; confirm at review).**
1. **Event shape** — extend `HoverEvent` with `value: float | None = None` (general,
   back-compatible) rather than a new `InspectEvent`. Native hover keeps `value=None`;
   raster hover sets `point_index=None, value=<agg>`.
2. **Retain + thread** — rasterizers return a `RasterResult(rgba, bounds, aggregate)`;
   `RasterAggregate` is a pure (Qt-free) value object with `value_at(x, y)`. Attached to
   the static `Image` (`_raster_aggregate`) **and** refreshed through the 4b
   `RasterController` via an injected `on_aggregate` callback + a shared holder, so
   hover values stay fresh after pan/zoom. `RasterTarget` stays unchanged.
3. **Categorical** — first cut returns total count per pixel (`kind="category"`);
   per-category breakdown deferred.
4. **Auto, not opt-in** — wired for datashaded Images only; throttled (33 ms),
   `value_at` is O(1).

**Scope.** Hover/inspect only — selection/brush on rasters, per-category value, and
webengine raster hover are out of scope (`capabilities-gaps.md` §2 Interaction).

**Status:** ✅ implemented — `HoverEvent.value` + `RasterResult`/`RasterAggregate`
(`ext/datashader.py`), controller `on_aggregate` freshness hook (`core/raster.py`),
pyqtgraph + matplotlib hover wiring; tests in `test_raster_inspect.py`. Spec +
offscreen-teardown hygiene note in `milestone-raster-inspect.md`.

---

**Context.** The bridge serializes payloads with `json.dumps` (`_send_now`). Big
figures / live data could overwhelm JSON; Arrow IPC is the faster binary path.

**Underlying.** JSON is fine for moderate payloads and is what works today. Arrow
IPC is a real win only at large payloads, and the roadmap already places it at
Phase 5 (W5), gated on a measured need rather than speculation.

**Recommendation.** Keep JSON for W0–W4; add Arrow IPC at W5/Phase 5 if a measured
big-payload need shows up.
**Status:** ◑ accepted-pending-revisit (per user) — JSON now; revisit Arrow IPC at
**W5/Phase 5** against a real big-payload measurement (<100 ms target).

---

## [D30] Webengine packaging + physical move + import shim

**Context.** The legacy code lives in `src/qtwebplot/`. The rehome moves it under
qtviz; how much moves when, and what happens to existing `qtwebplot` imports?

**Underlying.** A registered backend is just a *module* exposing
`name`/`capabilities`/`renderers`/`supports`/`render`/`can_host`
(`backends/__init__` registers the `pyqtgraph`/`matplotlib` backend modules), so
`webengine` is a module of the same shape under `src/qtviz/backends/webengine/`.
The reusable bridge core (`web_bridge_view`, `bridge`, `_runtime`, `_inject`) lifts
wholesale into `backends/webengine/_bridge/`; the per-library `ext/*` become
internal figure-hosts. Move scope: do the **whole package at once** in W0 (chosen) —
the legacy tests travel with it and keep proving the bridge on the new paths — vs. a
two-step move (bridge+Plotly first). One move is cleaner; the bigger diff is
acceptable. A top-level `qtwebplot` shim re-exports from the new location with a
`DeprecationWarning` (roadmap Phase 0/6). Packaging: `qtviz[webengine]` =
PySide6-WebEngine + per-library sub-extras (plotly/bokeh/holoviews).

**Caveat surfaced during the move:** the legacy WebEngine GUI tests
(`tests/test_layouts_gui.py`) time out offscreen today (7 failures). W0 must gate
them behind a "Chromium usable" skip so the suite isn't red on the new paths
(`webengine-rehome.md` §9).

**Recommendation.** Move all of `src/qtwebplot/` under `backends/webengine/` in W0;
keep a deprecating `qtwebplot` import shim; skip-gate the WebEngine GUI tests.
**Status:** ✅ resolved (per user) — whole-package move now + import shim; sequence is
`webengine-rehome.md` §8 W0.

---

## [D47] Datashader shading — split aggregate (theme-free) from shade (theme-aware)

**Context.** Shading was welded to aggregation in the theme-less pipeline (`tf.shade`
with vendored `_VIRIDIS`/`_CATEGORY10`), returning bare rgba — so no `Theme` was in
reach and no legend could be described ([D20] tension). This blocked all three
roadmap-§8.5 gaps at once (legend, theme colors, agg surface).

**Decision (✅ implemented).** Split `aggregate_element` (theme-free `Aggregate`
carrying the raw xarray agg + the [D46] `RasterAggregate`) from `shade_aggregate`
(theme-aware → rgba + `Legend`). `shade` is *injected* into `RasterController` the
same way `rasterize` already is, so `core/raster` stays palette-free; the backend
closes the theme over `themed_rasterize`. The raw agg is kept so re-shading runs
`tf.shade` faithfully (no numpy re-implementation of eq_hist/blend). Pipeline still
bakes a default-palette rgba as a safety net; themed backends re-shade from the
carried `Aggregate`. Alternatives: numpy re-implementation of shading (deferred —
faithful enough not worth the risk); thread theme into `resolve_node` (wrong layer).

**Status:** ✅ implemented (C1/C2) — `ext/datashader.py`, `core/raster.py`,
`milestone-datashader-coverage.md`.

---

## [D48] Legend honesty for eq_hist density vs value aggregations

**Context.** `count` density shades with `eq_hist` (histogram equalization) — a
non-linear color↔value map, so a linear colorbar with interior ticks would lie.

**Decision (✅ implemented).** `Legend.linear` flag. Density (`count`) keeps
`eq_hist` and renders an **endpoints-only** key (no interior linear ticks). Value
aggregations (`mean`/`sum`/`max`/`min`/`std`) default to `how="linear"` so the
colorbar's `vmin`/`vmax` are truthful. Categorical → a key legend, as native. The
default `how` is therefore kind-dependent (overridable).

**Status:** ✅ implemented (C3) — `core/encoding.Legend.linear`, both native legend
renderers, `shade_aggregate`.

---

## [D49] Aggregation-surface API — `Scatter.agg`

**Context.** Reductions were implicit (no `color_by`→count, numeric→mean,
categorical→by); no way to ask for max/sum/etc.

**Decision (✅ implemented).** `Scatter.agg: auto|count|sum|mean|max|min|std|any|by`,
default `"auto"` (back-compatible). `core._validate.check_agg` validates the
`(agg, color_by, scale)` triple — value aggs / `by` need `color_by`; any non-`auto`
agg needs `scale` ≠ native. Reducer map in `ext.datashader._reducer`; the agg name
flows into `Aggregate.kind` → legend title / hover label. Curve stays count-only (no
value column — deferred). Multi-agg `summary` deferred (forks shading/legend).

**Status:** ✅ implemented (C4) — `elements/scatter.py`, `core/_validate.py`,
`ext/datashader.py`.

---

## [D50] Theme palette source for the raster

**Context.** Which palette colors the key/ramp, and does a category match a native
`color_by`?

**Decision (✅ implemented).** Categorical key cycles `Theme.palette`; continuous
ramp uses the same continuous palette the native renderers pass (`viridis`).
Category→color is assigned by `core.encoding.category_swatches`, shared with native
categorical, so a category gets the *same* swatch as points or as a raster blend.
webengine re-shades with the theme too (C5); webengine *legends* deferred (it draws
no legends for any element yet).

**Status:** ✅ implemented (C2/C5) — `core/encoding.category_swatches`, backend
`_shade_raster`, webengine `_image_trace`.

---

> **Decisions [D51]–[D58] (post-0.1)** flow from `weakness-root-causes.md` (root causes
> R1–R6) and the staged 0.2→0.3→0.4 plan in `roadmap.md` §8. Each names the root cause
> it addresses and the milestone it lands in.

## [D51] Contract enforcement — honor-or-warn (make §3.4 real)

**Context.** R4: §3.4's honor-or-warn degradation was declared as data
(`REQUIRED/RECOMMENDED_OPTIONS`) but read by no code path, so accepted options were
silently dropped (`marker`, pyqtgraph `alpha`/`line_style`, `Heatmap.aggregator`,
`Bars.group`, `Image.interpolation`). The conformance suite only checked "doesn't
crash."

**Decision (0.2, planned).** Implement §3.4 as **honor-or-warn, never raise** (chosen
over fail-fast): a general `core/_degrade.check_recommended` seam at dispatch warns
**once** per `(backend, element_type, option)` for any non-default recommended option a
backend doesn't honor, via a per-backend `honored_options` declaration. **Honor the
trivial drops** so the warning stays truthful (wire `marker`/pyqtgraph
`alpha`/`line_style`/`interpolation`); **warn-and-degrade** the genuinely-unbuilt
(`aggregator`, `group`) until their features ship (0.4). A **conformance test** asserts
every element×option×backend is honored-or-warned — the anti-drift guard. Spec §3.4
updated; `milestone-0.2-hardening.md` §1.

**Alternatives weighed.** (a) *Implement-cheap + reject-rest + delete dead surface* —
fail-fast and honest, but breaks running code; rejected for the non-breaking
honor-or-warn. (b) *Reject all unhonored* — loudest, adds no features; rejected.

**Status:** planned (0.2).

## [D52] Capability honesty

**Context.** R4: `Capabilities` declares fields with no implementing path — `dimensions
= {2,3}` on matplotlib/webengine with no 3-D renderer (and `dimensions` is read by
nothing), `animation = True` with no animation API (§12 lists it out of scope).
Negotiation assumes capabilities don't lie.

**Decision (0.2, planned).** A declared capability must be backed by real code. Set
`dimensions={2}` and `animation=False` everywhere until an implementing path exists;
keep pyqtgraph's `exports` under-claim (safe). Add a capability-honesty conformance
test. 3-D recorded as a non-goal for now ([D58]). Spec §2.5 gets the honesty rule.

**Status:** planned (0.2).

## [D53] Native escape valve — `handle.native(element_id)`

**Context.** R1: the purity/value-hash invariant (Qt-free, immutable, hashable
Elements) structurally forbids putting a live `PlotItem`/`Axes` on an Element — the
same three reasons [D38] kept `Signal` off Elements — so the only escape hatch is
`RawFigure` (web-only, non-composable). Developers who hit the 8-element/5-event
ceiling have no way to reach backend-native power (ROIs, crosshairs, native signals).

**Decision (0.2, planned).** Add a **post-render accessor**
`RenderHandle.native(element_id) -> BackendPrimitive | None` (+ `View.native`
convenience; `CompositeRenderHandle` fans out). The live object is returned *through the
handle at render time*, **never stored on the Element**, so purity is untouched
(elements stay Qt-free/hashable; caches unaffected). Documented as **non-portable**.
Chosen over construction-time `.with_hooks` (keeps the Element model fully pure).
Backends retain an `element_id → primitive` map at render. Spec §2.8; `milestone-0.2-
hardening.md` §2.

**Alternatives weighed.** (a) construction-time hooks (HoloViews `.opts(hooks=)` style)
— declarative but adds an identity-keyed field to the Element; deferred. (b) live-item
RawFigure — violates purity; a non-goal ([D58]).

**Status:** planned (0.2).

## [D54] Element axis stays curated — registry deferred

**Context.** R3: backends and data-adapters are pluggable (registry + entry-point);
elements/events are closed sets. Adding one element ≈ 9 files across 3 renderers.

**Decision.** Keep the element vocabulary **curated/first-party** for now. **Grow
built-ins** through the normal process where there's clear demand — candidates:
`BoxPlot`/`Violin`, grouped/stacked `Bars`, a real `Heatmap.aggregator` reduction
(0.4). A public `register_element` + `qtviz.elements` entry-point + partial-support
(declared-degradation) tier is **explicitly deferred** (revisitable once third-party
demand is proven) — chosen over opening it now to preserve coherence and avoid a
negotiation-contract change. A declared-degradation tier may still be needed if a new
built-in lands on only some backends; scope it then.

**Status:** decided (curate now); registry parked.

## [D55] Legends become first-class

**Context.** R5: `Legend` is the return value of `map_colors` (a side-effect of the
color-mapping path), not an element — so only `color_by`-Scatter and rasters get one;
Curve/Bars/…/multi-series overlays get nothing; webengine renders none; stub fields
`OverlayOptions.legend`/`Options.label` are unwired.

**Decision (0.3, planned).** Introduce a per-element `legend_entry()` contribution
contract aggregated across an `Overlay`'s children; wire `OverlayOptions.legend` (+ a
position field) through the surface seam; enable webengine legends (`showlegend` +
per-trace `name`, emit colorbar from the currently-discarded `_legend`); swap
pyqtgraph's stepped swatch for a true `ColorBarItem` gradient. Single-surface only
(cross-pane legend depends on R6 → [D57]). Detailed milestone at 0.3 start.

**Status:** planned (0.3).

## [D56] Axes become first-class — `AxisSpec` + transform stage

**Context.** R5: axes were modeled as a cosmetic "surface" (title/labels); the resolve
pipeline produces concrete data-space arrays with no transform stage; `OverlayOptions`
has no scale/limit/tick concept. This is the roadmap's **Phase B** (already spiked).

**Decision (0.3, planned).** Add an `AxisSpec` (`scale: linear|log|symlog|time`, `lim`,
`invert`, `tick_format`) + `aspect` to `OverlayOptions`; thread `x_scale`/`y_scale`
through `RenderContext`; renderers apply a `_logify` helper; concentrate the cross-
backend coordinate reconciliation (risk R1 in `axis-surface-feasibility.md` §10 — the
`10**`/`log10` normalization at every event/state boundary) in pyqtgraph (~120–150
LOC); matplotlib ~1 line; webengine small. `time` accepted in the seam but gated on the
data layer carrying datetime dtype. Supersedes the original spec §3/§4 log-axis claim
struck by the Phase-B spike. Also unlocks datashader `logx`/`logy`.

**Status:** planned (0.3); spike done (`axis-surface-feasibility.md`).

## [D57] Composite export — raster composite; single vector cross-backend a non-goal

**Context.** R6: a layout is N independent backend widgets with a merged event bus and
**no unified scene**, so `CompositeRenderHandle.export` raises ([D11]) and there is no
cross-pane legend surface.

**Decision (0.4, planned).** Add a composite-level coordinator: composite **raster**
export via the container `widget.grab()` (one PNG) plus an opt-in per-pane export list;
the coordinator is also the future home for cross-pane chrome (legend). A single
**vector** surface across heterogeneous backends is **intrinsic and a non-goal**
([D58]) — accept it.

**Status:** planned (0.4).

## [D58] Accepted limits / non-goals (the abstraction's documented edges)

**Context.** R1/R6: some weaknesses are intrinsic to invariants we are keeping
(`weakness-root-causes.md` §7). Documenting the edges prevents re-litigation and tells
users where to reach for `native()`.

**Decision (documented, revisitable).** Current non-goals: (1) a **live native item on
an Element** — use `handle.native()` ([D53]) instead; (2) **cross-backend Overlay**
(single composited overlay across backends, already §12); (3) a **single vector export
across mixed-backend layouts** (raster composite only, [D57]); (4) **3-D rendering**
([D52], §12); (5) **pixel→source-rows through a datashaded raster** — blocked on the
Phase-5 `DataSource`/predicate-pushdown layer, sequence there. Spec §12 updated.

**Status:** documented; each revisitable with evidence.

---

## [D59] Axes 0.3 scope, rollout & edge policy

**Context.** DP4/[D56] makes axes first-class (R5). The full design is in
`axis-surface-feasibility.md`; the open sub-decisions were scope, rollout shape, and
edge policy.

**Decision (0.3, planned).** Scope = feasibility **Phases B + C**: `AxisSpec` with
`scale ∈ {linear, log, symlog}`, `lim`, `invert`, plus `aspect`; `Capabilities.scales`
+ warn-fallback. **Defer** the tick-format vocabulary (Phase D) and `time`/datetime
(blocked on the data layer). **Rollout = all-at-once** — log on all three backends in
one increment (mpl easy, webengine small, pyqtgraph Approach A: pre-`log10` data +
`AxisItem.setLogMode`), preserving "renders identically." Build the **R1 coordinate
normalization** (§10.3) *with* log, never after. Edge policy: non-positive-under-log →
**drop + warn**; datashader + non-linear → **warn + render linear**; `AxisSpec.lim`
sets initial range, a live `ViewState` wins after rebuild; `symlog` included to
exercise the gate. `milestone-0.3-firstclass.md` §1.

**Alternatives weighed.** Staged B1→B2 (smaller PRs, but the default backend goes
temporarily linear — rejected for the "describe once" cost); per-element axis field
(rejected — bloats Element, feasibility §2.2).

**Status:** planned (0.3).

## [D60] Legend as a per-element contract (realizes [D23]'s deferral)

**Context.** R5: `Legend` is only the return value of `map_colors`, so only
`color_by`-Scatter and rasters get one; multi-series overlays get nothing;
`OverlayOptions.legend`/`Options.label` are unwired; webengine draws no legend.

**Decision (0.3, planned).** Add `Element.legend_entry(theme) -> LegendEntry | None`
(returns swatch+label for a single-color element; `None` for a `color_by` Scatter that
emits its own) + an optional `label` field on the styling elements + Overlay
aggregation into one legend via the existing `add_legend` path. Wire the dead
`OverlayOptions.legend` (+ a small `legend_position` vocabulary). webengine: flip
`showlegend`, emit a colorbar from the discarded `_legend`. pyqtgraph: a true
`ColorBarItem` gradient (replacing the 5-stop swatch). A placeable `Legend` *element*
is deferred — the contract covers 0.3. `milestone-0.3-firstclass.md` §2.

**Alternatives weighed.** Keep legends a side-effect (status quo — no multi-series
legends); full `Legend` element now (deferred — more than 0.3 needs).

**Status:** planned (0.3).

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
| D21 | dynamic viewport re-aggregation seam | Phase 4b | ✅ RasterController + RasterTarget (all three: pyqtgraph + matplotlib; webengine 2026-08-05 via `plotly.view` bridge feed + PNG-source restyle) |
| D22 | datashader coverage (lines, categorical color) | Phase 4 | ✅ points + lines + value/categorical agg; deeper gaps → `capabilities-gaps.md` |
| D23 | color/size encoding — shared mapping + legends | toward HoloViews | ✅ `core/encoding.py`; native `Scatter` `color_by`/`size_by` + auto legend (`milestone-color-encoding.md`) |
| D24 | webengine default Element renderer (Plotly vs Bokeh) | webengine rehome | ✅ resolved — Plotly the only Element renderer; Bokeh a `RawFigure` host |
| D25 | webengine async render contract | webengine rehome | ◑ handle-now + command queue **firm**; loading-placeholder pending-revisit |
| D26 | raw-figure passthrough element vs escape hatch | webengine rehome | ✅ resolved — first-class `RawFigure` element (negotiates only to webengine) |
| D27 | webengine event/selection fidelity mapping | webengine rehome | ✅ resolved — per-element `SelectEvent` routing (matches native pyqtgraph); lands W3a |
| D28 | `from_holoviews` fallback to webengine | Phase 3 (depends D26) | ◑ principle accepted; wiring pending-revisit (Phase 3) |
| D29 | webengine transport (JSON now, Arrow IPC later) | webengine rehome / P5 | ◑ JSON now; Arrow IPC pending-revisit (W5/P5) |
| D30 | webengine packaging + physical move + import shim | Phase 0/6 | ✅ resolved — whole-package move now + `qtwebplot` shim; skip-gate GUI tests |
| D31 | `RawFigure` passthrough design (detect/host/compose) | webengine W3 | ✅ resolved — auto-detect + `kind=`; backend render-branch; standalone (Layout pane in W4) |
| D32 | W3 event-translation split (Plotly W3a, Bokeh W3b) | webengine W3 | ✅ resolved — W3a Plotly + RawFigure render-all + per-element select; W3b Bokeh events |
| D33 | webengine W5 transport (base64 → scheme handler) | webengine W5 | ✅ resolved — base64 (W5.1) → custom `qtviz://` scheme handler (W5.2); benchmark first |
| D34 | webengine W5 binary format | webengine W5 | ✅ resolved (revised) — **raw typed-array buffers**, no apache-arrow (numeric-only payload + offline) |
| D35 | webengine W5 figure-splitting + Plotly typed-array API | webengine W5.1 | open — spike Plotly's `{dtype,bdata}` ingestion; then design `_figure` split + JS reassembly |
| D36 | webengine W5 custom-scheme registration timing | webengine W5.2 | open — decide when/where to register the scheme (before QApplication) |
| D37 | **qtviz runs 100% offline — no CDN, ever** | spec §0.1 / webengine | ✅ accepted — bundle JS locally (inline now, `qtviz://` in W5.2); HTML has no external URL |
| D38 | reactivity binds at View root, not in Elements | reactive (Phase 4) | ✅ accepted — Option B: `View(Signal[Node])`; Elements stay pure; sugar later |
| D39 | reactive runtime — auto-track, sync, simple+batch | reactive (Phase 4) | ✅ accepted — S-style auto-tracking; defer topological glitch-freedom |
| D40 | reactive render / threading / lifecycle | reactive (Phase 4) | ✅ accepted — debounced rebuild; `run_on_gui`; `Disposable` + View-owned + `owner=` |
| D41 | **Spike-P2 — HoloViews adapter feasibility (Phase 3 gate)** | Phase 3 | ✅ GO — 10/10 render via pyqtgraph on public API only (no internals); findings deferred to Phase 3 |
| D42 | hv `Histogram`/`Spread` shape handling | Phase 3 | ✅ accepted — `Histogram`→`Bars`, `Spread`→`Spread` via Expression `y±Δ`; no API change |
| D43 | `hvplot` integration mechanism | Phase 3 (3b) | ✅ decided — Path A (thin `from_hvplot` + docs; optional `[hvplot]` extra); B deferred; C rejected |
| D44 | `DynamicMap`/stream scope for 0.1 | Phase 3 (3b) | ✅ decided — L1 one-way (DynamicMap→`Signal[Node]`, kdims as Signals); L2 deferred; stream-only → warn-and-static |
| D45 | HoloViews import crashes offscreen-Qt teardown | Phase 3 / test infra | open — mitigated (importorskip order); lazy hv import at impl |
| D46 | Raster reverse-lookup — hover/inspect value on a datashaded view | Phase 4 (datashader) | ✅ implemented — `HoverEvent.value` + `RasterResult`/`RasterAggregate`, fresh through 4b controller; pyqtgraph + mpl hover wiring |
| D47 | Datashader aggregate/shade split (theme-free → theme-aware) | §8.5 datashader | ✅ implemented — `aggregate_element`/`shade_aggregate`; `shade` injected like `rasterize` |
| D48 | Legend honesty — eq_hist density vs linear value bar | §8.5 datashader | ✅ implemented — `Legend.linear`; density endpoints-only, value aggs linear `how` |
| D49 | Aggregation-surface API — `Scatter.agg` | §8.5 datashader | ✅ implemented — `auto/count/sum/mean/max/min/std/any/by`; `check_agg` triple-validates |
| D50 | Theme palette source for the raster | §8.5 datashader | ✅ implemented — `category_swatches` shared native↔raster; all 3 backends theme colors |
| D51 | **Contract enforcement — honor-or-warn (make §3.4 real)** | 0.2 / R4 | planned — wire trivial honors; warn-once for gaps; conformance guard; never raise |
| D52 | Capability honesty (no aspirational flags) | 0.2 / R4 | planned — `dimensions={2}`, `animation=False` until real; honesty test |
| D53 | **Native escape valve — `handle.native(element_id)`** | 0.2 / R1 | planned — post-render accessor; live object off the Element (purity intact); non-portable |
| D54 | Element axis stays curated; registry deferred | R3 | decided — grow built-ins (Box/Violin/grouped bars, 0.4); `register_element` parked |
| D55 | Legends become first-class | 0.3 / R5 | planned — `legend_entry()` + overlay aggregation + webengine + gradient bar |
| D56 | Axes first-class — `AxisSpec` + transform stage | 0.3 / R5 (= Phase B) | planned — scale/lim/invert/tick; R1 normalization in pyqtgraph; spike done |
| D57 | Composite export — raster composite; vector cross-backend non-goal | 0.4 / R6 | planned — container `grab()` + per-pane list; cross-pane chrome coordinator |
| D58 | Accepted limits / non-goals (documented edges) | R1/R6 | documented — live-item-on-Element, cross-backend overlay, cross-backend vector export, 3-D, raster→rows |
| D59 | **Axes 0.3 scope/rollout/edge policy** | 0.3 / R5 (= Phase B+C) | planned — log/symlog/lim/invert/aspect; all-at-once log + R1 normalization; drop+warn non-positive; defer tick-format/datetime |
| D60 | **Legend as a per-element contract** | 0.3 / R5 | planned — `legend_entry()` + `label` field + Overlay aggregation; wire `OverlayOptions.legend`; webengine legends; pyqtgraph gradient colorbar |
