# Retrospective at 1.0 — what I'd want the next session to know

> Written 2026-07-24, immediately after tagging `v1.0.0`, by the pair that
> implemented the 0.3→1.0 arc in one sustained push. This is the
> forward-looking sibling of `developer-perspective-weaknesses.md`: not what's
> wrong, but what proved load-bearing, where the bodies are buried, and where
> the real value lies next. Opinions marked as such.

## 1. What actually made the velocity possible

Worth naming, because these are *reusable practices*, not luck:

- **Machine-enforced honesty beats convention.** Every cultural rule that
  mattered ended up as a failing test: honor-or-warn (conformance matrix),
  capability honesty, R1 data-space seams, legend truthfulness, docs drift
  (`__all__` ⊆ api.md), and now the API freeze. When 0.6 needed to back
  `streaming=True` with real code, the *precedent* made it non-negotiable.
  Any new invariant should get its guard test in the same increment — the
  guards are cheap and they compound.
- **The seams were real.** Almost nothing in 0.3–0.6 required touching the
  core contracts: axes rode `surface_of`/`apply_surface` (built in Phase A
  *before* it was needed), streaming rode `DataRef.subscribe` (designed in
  Phase 1, dead for five versions), viewport regrid rode `RasterController`
  wholesale. **The pattern: when a capability is deferred, leave its seam in
  the contract.** Every "dead field" this project ever shipped eventually
  either got wired or got deleted with a warning — both outcomes were cheap
  because the seam existed.
- **Spike before committing on the risky increment.** The axis-surface
  feasibility spike (§10, done before this arc) made the scariest work of the
  whole run — pyqtgraph log + R1 — mechanical. The one place I spiked mid-work
  (zarr chunk I/O under strided reads) *changed the spec's claim* before the
  code shipped a lie. Do this every time a milestone has one load-bearing risk.
- **Decision numbering ([D59]–[D82] this arc) is cheap and pays constantly.**
  Grep-able rationale beat re-litigating every trade-off.

## 2. Load-bearing patterns to protect

Future changes should treat these as architecture, not implementation detail:

- **The private-stash pattern** (`_raster_source`, `_grid_source`): the resolve
  pipeline replaces an element's data with a snapshot but stashes the original
  lazy/source ref via `object.__setattr__` — excluded from value identity, so
  purity holds while the render layer gets the live handle it needs. Any
  future "the renderer needs to know where this came from" problem should use
  this, not a new Element field.
- **`RasterController` is the universal viewport loop.** Datashader points,
  gridded regrid — and, plausibly next, streaming rasters — are all "rasterize
  fn + target" instances of one debounce/off-thread/stale-drop machine. Do not
  fork it; inject into it.
- **`series_index_map` is the single source of palette truth.** The 0.4 bug it
  fixed (native backends drew every default series `palette[0]` while webengine
  cycled, and legend swatches lied) existed precisely because three backends
  each had an opinion. Anything color-slot-related goes through it.
- **The fallback ladder for live updates** (`set_element_data` → `handle.
  update` → `View._rebuild`) degrades explicitly at every rung. Extending
  streaming to more item types means implementing rung 1 for them — never
  bypassing the ladder.

## 3. Known soft spots (honest, not yet worth fixing)

Things I noticed and deliberately left; the next person should know they're
there before building on top:

- **`PgRenderHandle.update()` re-adds plots into the same
  `GraphicsLayoutWidget`** after clearing items but not removing the old
  PlotItems from the layout grid. For the covered paths (tests pass, same
  cell coordinates) it behaves, but it smells like widget stacking under
  repeated multi-cell updates. If reactive/streaming rebuild frequency ever
  rises on Layouts, audit this first.
- **Stream + datashader routes to the rebuild fallback** (0.6 risk 5,
  documented): a `scale="datashader"` element over a stream re-rasterizes via
  full update every tick. Works, but it's the obvious next performance cliff.
  The clean fix is a streaming-aware rasterize fn on `RasterController`.
- **webengine categorical `color_by` has no legend key** (needs one trace per
  category — deferred in 0.4 increment 4 with a note). Continuous got its
  real colorbar; categorical is the asymmetry.
- **No webengine viewport-regrid loop** (0.5): lazy grids on webengine render
  the static decimated raster only. Fine until someone puts a huge zarr on a
  webengine pane and zooms.
- **Bars under log-y use the "heights log10'd, baseline = data 1" convention**
  (documented in-code). Honest but visually surprising; a clipped-baseline
  treatment is the proper fix if bar+log demand appears.
- **`examples/README.md` and the README examples index don't list example 34**
  (and the README example list predates 31–34 generally). Pure docs debt.
- **`_StreamBinding` × reactive root**: a `qv.stream` *inside* a
  `View(Signal[Node])` root is untested. Both mechanisms are tick-coalesced so
  it should compose, but "should" is doing work in that sentence.
- **mypy is honest but shallow** in the renderer modules (scoped
  `disable-error-code` headers for the post-resolve shape invariant). If
  anyone ever types the Element→Ref relationship properly (generics or
  per-shape element bases), those headers should shrink.

## 4. Where the real value is next (opinion, ranked)

1. **1.1 housekeeping** (small): remove `Options` (promised), list example 34
   in the indexes, consider the `PgRenderHandle.update` audit above.
2. **Streaming × datashader** — the two flagship capabilities don't compose
   efficiently yet, and the composed thing ("a live feed of millions of
   points, datashaded, brushable") is exactly the library's one-sentence
   vision. Most of the machinery exists; it's a rasterize-fn + dirty-window
   problem.
3. **Hover/inspect for regridded arrays** — the datashader path has
   `HoverEvent.value` ([D46]); the 0.5 regrid path stores the visible window
   in `RegridResult.aggregate` but never wires hover. Symmetry is cheap here.
4. **Studio** — the standing exploration. Post-0.6 the substrate argument is
   much stronger than when it was first deferred: streams, crossfilter,
   screen-cost arrays, and composite export are precisely a dashboard app's
   primitives. If Studio happens, it should be a *thin* shell over signals +
   Views — the library now genuinely contains the hard parts.
5. **Parked items in rough order of pull**: twin axes (real audience demand
   signal per the mpl review) > contour/quiver > HoloViews L2 > webengine
   W5.2 binary transport (still gated on a real measurement, correctly) >
   element registry (needs a third party to exist first — repo is private
   forever, so possibly never).

## 5. Notes on the working relationship with this codebase

For whoever (or whatever) works here next:

- **The suite is the spec.** 540 tests, and the tier system means you can run
  meaning-level checks in seconds. Write the failing test first; the codebase
  is shaped so that's genuinely easier than not doing it.
- **Surface changes are three-file edits by design**: the change, the freeze
  list (`test_api_freeze.py`), and the CHANGELOG — plus `docs/api.md` if it's
  a new name (the drift guard will remind you). This friction is intentional;
  don't engineer around it.
- **R1 bites every new coordinate.** Any new event, state field, or gesture
  that carries a position must answer "which space?" — and the answer must be
  data space at the seam. The §10.3 table in `axis-surface-feasibility.md` is
  the checklist.
- **Respect the owner's standing rulings** (memory + design docs): private
  forever, no PyPI, no CI resurrection, datetime axes parked, pacing —
  direction gets confirmed at milestone boundaries, not assumed.
- **The cadence is the contract**: spec → discussion items ([Dxx], recommended
  + alternatives) → TDD increments with a commit at each green boundary →
  benchmarks → acceptance. Every milestone in this arc shipped that way, and
  the two times a test failed surprisingly, the cadence caught a real bug
  (the series-color lie; the zarr chunk-I/O claim) rather than a test typo.
