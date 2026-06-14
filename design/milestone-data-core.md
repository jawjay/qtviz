# Milestone — Data core hardening (lazy-first, out-of-core)

> Focused plan to make the data layer "as strong as possible" before lazy
> adapters (dask/xarray/zarr) land on top. Umbrella: `development-plan.md`;
> contract: `spec.md` §2.1 + §6. References `discussion-items.md` as **[D#]**.
>
> Thesis: the `DataRef` *contract* is sound, but the lazy *pipeline* it
> promises (§6.2 "narrow → materialize") is currently hollow — `select`/
> `window`/`materialize` are no-ops and the render path never materializes.
> This milestone builds that pipeline and proves it with dask.

## 1. Goal

A data core that renders the same Element from a `dict` or a billion-row,
out-of-core dask frame — pushing projection + windowing **down** into the
container and computing only the visible slice, off the GUI thread — with an
adapter conformance suite that pins the contract for every adapter.

## 2. Current gaps (honest review)

| # | Gap | Impact |
|---|-----|--------|
| G1 | `select`/`window`/`materialize` return `self` — no real narrowing/compute | the §6.2 pipeline doesn't exist; renderers pull full data |
| G2 | No materialize step in `render_root`/View | a lazy ref blocks the GUI thread (or can't render) |
| G3 | No async orchestration (D3 deferred) | can't compute off-thread, no placeholder, no re-entrancy |
| G4 | Data binding is string-columns only | no derived/computed channels; and (see [D14]) projection pushdown was going to be hand-rolled instead of delegated to the container |
| G5 | `fingerprint` = `id(buffer)` only | lazy refs (dask) need a deterministic token; narrowed refs collide |
| G6 | Adapter conformance is one equivalence test | the contract isn't pinned the way backends are |
| G7 | Shape bridging (1-D gridded → tabular) undefined | xarray 1-D DataArray can't serve a Scatter |
| G8 | No entry-point discovery | third-party adapters can't auto-register |

## 3. The strengthened contract (`DataRef`)

```python
class DataRef:
    is_lazy: bool
    def schema(self) -> Schema: ...
    def size(self) -> int | None: ...                 # cheap/estimated; None if unknown
    def extent(self, name) -> tuple[float,float]|None  # metadata or None for lazy
    def resolve_channels(self, channels: dict[str, Accessor]) -> dict[str, ndarray]
                                                       # apply accessors to native, compute together
    def window(self, **ranges) -> DataRef              # REAL narrowing (§3.3 below)
    def fingerprint(self) -> Hashable                  # buffer id | dask token | version
    def subscribe(self, cb) -> Disposable
    def native(self) -> Any                            # escape hatch (Datashader) + callable target
    def materialize(self, limit: int | None = None) -> DataRef   # → eager; BLOCKING compute
```

Changes from today (and the **[D14] accessor reframe**):
- **Data binding is functional.** A channel maps to an `Accessor =
  str | Expression | Callable | ArrayLike` ([D14]); `x="a"` is sugar for
  `col("a")`. `Expression` is a first-class, qtviz-owned serializable AST
  (`col("a")+col("b")`, `col("p").log()`, `(col("x")>=0)&(col("y")<10)`) — the
  preferred derived/transform/predicate accessor; `Callable` is the escape hatch.
  `resolve_channels` applies each accessor to the (lazy) native object and
  computes them together — so the **container** does projection pushdown
  (`ddf["a"]+ddf["b"]` reads only a,b). This **replaces `select(names)` and
  `Element.columns()` entirely**; `select` is dropped.
- **`window`** stays as a real lazy-safe narrowing primitive (§3.3); the
  viewport→window trigger is deferred ([D16]).
- **`materialize(limit=None)`** is a *blocking* compute returning an eager ref.
  Eager → `self`. `limit` caps rows for safety/preview. The **pipeline** (not the
  ref) runs it on a Worker — so `materialize`/`resolve_channels` stay pure,
  thread-safe computes.
- **`fingerprint`** is adapter-specific and must change when narrowing changes the
  data: `id()` for in-memory, `dask.base.tokenize` for dask, version counter for
  `Signal` (Q-O). Element value-identity treats `str`/array accessors by
  value/fingerprint and `Callable` accessors by identity (D14).

### 3.3 `window` semantics

`window(**ranges)` takes **name-keyed** ranges and narrows:
- **Tabular**: a row predicate — `window(time=(0,10))` keeps rows where column
  `time ∈ [0,10]`. Multiple names AND together.
- **Gridded**: a coordinate-range slice — `window(x=(0,10))` slices the `x` dim.

The *automatic* viewport→window trigger (zoom → re-window → re-materialize) is the
Phase 4 reactive/Datashader piece and is **out of scope here** — this milestone
builds `window` as a correct, lazy-safe primitive; nothing calls it on zoom yet.

## 4. The async materialize pipeline (resolves [D3])

The core new machinery. A cheap GUI-thread narrowing pass, then a Worker compute.

```
render_root(node)
   │  plan(node)                        # GUI, cheap: collect each Element's channels(); is any ref lazy?
   ▼
 any lazy? ──no──► resolve_node (cheap, all eager) ──► backend.render
   │ yes
   ▼
 show placeholder ; Worker.submit(resolve_node) ──► (GUI) re-render w/ resolved node
                                        ▲ build-id guards: stale results dropped
```

- **`Element.channels() -> dict[role, Accessor]`** ([D14], G4): each Element maps
  its fixed roles (`x`, `y`, `color`, `size`, `values`, …) to accessors. Replaces
  the abandoned `COLUMN_FIELDS`/`columns()`.
- **`resolve_node(node)`** (Worker for lazy, cheap for eager): per Element, call
  `ref.resolve_channels(el.channels())` → `{role: ndarray}`, and replace the
  Element's data with a small eager ref keyed by role (via `with_`). The container
  does projection pushdown when accessors hit the lazy object; computing all
  channels together shares subgraphs. The expensive step; safe off-thread.
- **Renderers read by role** — `data.series("x")` — never seeing the accessor, so
  string / lambda / array bindings are indistinguishable downstream.
- **View** owns the orchestration: placeholder while pending, a monotonic
  `build_id` so a newer `set_root`/`set_backend` drops stale results, and error
  surfacing if resolution raises (bad accessor, length mismatch, compute error).

## 5. Adapter conformance suite (the keystone, G6)

The artifact that makes the core "strong." Parametrized over **adapter cases** —
each the *same logical data* in a different container — every adapter must pass:

```python
TABULAR_CASES = ["dict", "pandas", "arrow", "dask"]      # + polars later
GRIDDED_CASES = ["ndarray", "xarray", "zarr", "dask_array"]

# for every case that imports:
#   schema names/dtypes/shape correct
#   resolve_channels({"x": "a", ...}) ≡ the reference numpy arrays (cross-adapter)
#   resolve_channels with EXPRESSION (col("a")+col("b")) and CALLABLE accessors
#       both work + agree with the eager reference
#   Expression: to_dict/from_dict round-trips; columns() reports referenced names
#   size correct or None; extent correct or None; window narrows rows/coords
#   LAZY invariant: resolve_channels reads ONLY referenced columns (assert via a
#       counting/mock dask scheduler — projection pushdown); materialize computes
#   fingerprint: stable, distinct per data object
```

This is the data-side mirror of the backend conformance suite — "adding a
container is one adapter file" becomes executable.

## 6. Shape model (resolves [D7-data] / residual D1)

**Adapters pick the shape; refs don't bridge.** A 1-D xarray `DataArray` is wrapped
as a `TabularRef` (dim → a column, values → a column); a 2-D+ one as a `GriddedRef`.
Structured ndarray → tabular, plain ndarray → gridded (as today). So Scatter on a
1-D DataArray works because the adapter handed it a tabular ref — no ref-level
bridging, no Element changes.

## 7. Entry-point discovery (G8)

`as_data_ref` registry also loads adapters advertised under the
`qtviz.data_adapters` entry-point group at import, so third-party container
support is publish-and-install (mirrors the planned backend entry point).

## 8. Build order

> **Status: data-core hardening complete.** step 1 ✅ (accessors) · step 2 ✅
> (async View orchestration, D13) · step 3 ✅ (adapter conformance suite) ·
> step 4 ✅ (**dask** — `resolve_channels` delegates to `dask.compute` for
> pushdown + shared subgraphs) · step 5 ✅ (**xarray** DataArray/Dataset +
> **zarr**, lazy off-thread, `qv.tabular()`/`qv.gridded()` shape overrides, D17).
> Conformance covers dict/numpy/pandas/arrow/dask/xarray (tabular) and
> ndarray/xarray/dask/zarr (gridded). D15–D17 accepted (D15 backend-aware warn +
> Datashader auto-route land in Phase 4). Remaining: `qtviz.data_adapters`
> entry-point discovery (small) → then Phase 4 (Datashader, reactive Signals).


1. **Accessor model** ([D14]): `Accessor = str | Expression | Callable |
   ArrayLike` + the `Expression` AST (`col`, arithmetic, comparison/boolean,
   literals, a starter set of numpy-ufunc transforms, `to_dict`/`from_dict`,
   `columns()`), `Element.channels()`, and `DataRef.resolve_channels()` on the
   eager refs — plus `resolve_node` wiring the pipeline. Renderers switch to
   reading by role. Eager-only first (all four accessor kinds work; pushdown is
   a no-op for in-memory but the seam is tested).
2. **View async orchestration** (placeholder, build-id, Worker) — exercised with
   a *synthetic* lazy stub ref (no dask dep) so the async path is deterministic.
3. **Adapter conformance suite** (§5) over the eager adapters + the synthetic
   lazy stub (incl. a callable-accessor case).
4. **dask adapter** (`dask.DataFrame` tabular, `dask.array` gridded) — the proof;
   activates the lazy conformance cases and the existing skipped lazy test.
5. **xarray + zarr adapters** (gridded; xarray 1-D → tabular per §6).
6. `fingerprint` via `tokenize`; entry-point discovery.

Datashader (consume `native()` for aggregate→ImageItem) stays a later Phase-4
item — it sits on top of this core.

## 9. Acceptance

- The async pipeline renders a synthetic-lazy Element off-thread with a
  placeholder, and drops stale materializations under rapid `set_root`.
- The adapter conformance suite is green for dict/pandas/arrow + the lazy stub;
  it goes green for dask the moment that adapter lands — with the laziness
  invariant (narrow doesn't compute) asserted via a counting scheduler.
- A ≥1M-row dask frame renders through pyqtgraph without freezing the UI.

## 10. Key decisions (need alignment — see discussion-items D13–D17)

- **[D13]** async UX: placeholder vs keep-last-render while materializing; error display.
- **[D14]** ✅ **accepted** — functional data binding: a channel is an `Accessor`
  (`str | Expression | Callable | ArrayLike`), applied to the data object; the
  container does pushdown, so `select`/`columns()` are dropped. `Expression` is
  first-class (serializable AST); `Callable` is the code-only escape hatch.
- **[D15]** materialize safety: guard when materializing an un-windowed huge lazy
  ref (warn / route to scale strategy / hard `limit`).
- **[D16]** confirm viewport→window auto-trigger is deferred to Phase 4 (this
  milestone ships `window` as a primitive only).
- **[D17]** confirm shape-by-adapter (no ref bridging) per §6.
