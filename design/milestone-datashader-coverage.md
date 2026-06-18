# Milestone — Remaining Datashader coverage (roadmap §8.5)

> Turn a datashaded view from a *bare image* into a *publishable, themed plot*.
> Today a `Scatter`/`Curve` with `scale="datashader"` aggregates correctly but
> renders as an RGBA `Image` with **no legend**, **fixed default colors** (not the
> View's `Theme`), and **only `count`/`mean`/`by(count)` reductions**. This
> milestone closes those three gaps. Companion to
> `milestone-phase4-datashader.md` (the path this extends) and
> `capabilities-gaps.md` §1 (the gap register this drains). References
> `discussion-items.md` as **[D#]**; new items **[D47]–[D50]** below are
> *recommended; confirm at review* (then promote to `discussion-items.md`).

## 0. Status — as built (2026-06-17)

All five sub-milestones shipped on `datashader-coverage`; full suite green (369
passed), ruff clean.

| Step | What landed | Tests |
|------|-------------|-------|
| **C1** ✅ | `aggregate_element` / `shade_aggregate` split; `Aggregate` carries the raw xarray agg + the [D46] `RasterAggregate`. Golden-rgba guard pins zero pixel drift. | `test_datashader_shade.py` (golden + decomposition) |
| **C2** ✅ | `shade_aggregate` takes `palette`/`continuous_palette`; `core.encoding.category_swatches` is the shared category→color source; backends re-shade the raster with `ctx.theme`; `themed_rasterize` injected into the controller. | shade-level + rendered-raster wiring |
| **C3** ✅ | `RasterResult.legend` (a `core.encoding.Legend`); backends draw it via the **existing** `add_legend`/`_add_legend`; idempotent (replace-not-stack); `Legend.linear=False` → eq_hist density shows endpoints only ([D48]); `RasterController.on_legend` refreshes on zoom. | legend-build + render + no-stack |
| **C4** ✅ | `Scatter.agg` (`auto/count/sum/mean/max/min/std/any/by`); `core._validate.check_agg` validates the `(agg, color_by, scale)` triple; reducer map in `ext.datashader._reducer`. Curve stays count-only (no value column — deferred). | reducer correctness + validation |
| **C5** ✅ | webengine `_image_trace` re-shades with the theme (parity with native). **Deferred:** webengine *legends* — webengine renders no legend for any element yet (native `color_by` included; layout `showlegend=False`), so a raster-only legend would be a one-off; tracked as a broader webengine-legend gap. | `test_webengine_raster_uses_theme_palette` |

Deviations from the plan: (a) the shade benchmark target was unrealistic — see §5;
(b) C5 narrowed to theme colors (legends deferred, rationale above).

## 1. Scope

**In scope** — the three items the roadmap names for §8.5:

1. **Legend / colorbar for the raster** — a category key for `by`, a colorbar for
   continuous value aggregations, a density key for `count`.
2. **Theme-driven colors** — the categorical key and continuous ramp come from the
   View's `Theme`/`Palette`, so a datashaded `color_by` matches a native one.
3. **Wider aggregation surface** — `sum`/`max`/`min`/`std`/`any` (and explicit
   `count`/`mean`/`by`) selectable per element, not just the implicit default.

**Explicitly out of scope** (kept here so the seam doesn't accidentally bake them
out — each is a clean follow-on once the aggregate/shade seam below exists):

- **Line width / antialiasing / categorical lines** under datashader — Curve
  styling. Slots into the `shade` step + the `agg` plumbing later.
- **Gridded regrid** (`canvas.raster` for huge `Image`/`Heatmap`) — a new glyph,
  not a shading/agg concern; separate milestone.
- **`spread`/`dynspread`** for sparse zoomed pixels — a post-aggregation `tf` op;
  *naturally lands in the new `shade` step*, but its element-API exposure is
  deferred (note in [D47]).
- **Log / datetime axes** (datashader `logx`/`logy`) — belongs to the
  **axis-surface seam** (roadmap §8.3 Phase B), not here.
- **Multi-aggregate `summary`** (e.g. count+mean in one pass) — produces multiple
  planes and forks shading/legend; deferred (note in [D49]).
- **Static single-hue `color` tint** under datashader — by design ignored; trivial
  add later via the `shade` step.

## 2. The core architectural move — split *aggregate* from *shade*

Why all three gaps share one root: **shading happens in the theme-less pipeline.**
`ext/datashader.py::_aggregate_and_shade` runs `tf.shade(...)` with hard-coded
`_VIRIDIS`/`_CATEGORY10` and returns only `(rgba, bounds, aggregate)` — so there is
no `Theme` in reach (it lives at render time, in the backend) and no description of
*what the colors mean* (so no legend can be drawn). [D20] already flagged this
tension and named "raw-aggregate + theme colormap" as the future form.

So: **separate the theme-free aggregation from the theme-aware shading**, and make
the shade step emit the same `core.encoding.Legend` the native renderers already
know how to draw.

```
            ┌─────────────────── theme-free, lazy, off-thread ───────────────────┐
 source ──► aggregate_element(el, w,h, x_range,y_range) ─► Aggregate(agg, values, bounds, kind, categories)
            └────────────────────────────────────────────────────────────────────┘
                                              │  (carried on the Image; re-run by the 4b controller)
                                              ▼
            ┌──────────── theme-AWARE, at render time (backend supplies palette) ──┐
            shade_aggregate(Aggregate, palette, continuous_palette, how) ─► (rgba, Legend)
            └──────────────────────────────────────────────────────────────────────┘
                                              │
                          ┌───────────────────┴───────────────────┐
                          ▼                                        ▼
            target.set_raster(rgba, bounds)            add_legend(axes, Legend, theme)
                  (existing seam)                       (existing native legend path!)
```

**Three properties this buys us:**

- **Theme flows through the existing injection seam, not a new dependency.**
  `core/raster.py` already injects `rasterize` "so this module stays free of any
  datashader dependency." We inject `shade` the same way "so core stays free of any
  theme/palette dependency." The backend, which *has* `ctx.theme`, supplies
  `shade=lambda agg: shade_aggregate(agg, palette=ctx.theme.palette, …)`.
- **Legends are nearly free.** `shade_aggregate` returns a `core.encoding.Legend`
  (the exact type from §1's `Legend`), and both backends already render it
  (`pyqtgraph/_legend.py::add_legend`, `matplotlib/_renderers.py::_add_legend`).
  The raster legend reuses that path verbatim.
- **One shading rule, native ↔ raster.** `core/encoding.py`'s docstring already
  promises "same palette → color key / ramp … so a column colors the same way
  however it is drawn." This makes that *actual*: the categorical key and continuous
  ramp are derived from the same `Theme.palette` the native `Scatter` `color_by`
  uses, so the two paths match pixel-for-legend.

**Fidelity decision (see [D47]):** `shade_aggregate` keeps the raw datashader
aggregate (xarray) and calls `tf.shade` on it — it does **not** re-implement
`eq_hist`/categorical-blend in numpy. So `Aggregate` carries the xarray `agg`
(theme-free) alongside the pure-numpy `RasterAggregate` (which stays exactly as-is
for [D46] hover — unchanged, still Tier-1 testable).

### 2.1 What changes, file by file

| File | Change | Risk |
|------|--------|------|
| `ext/datashader.py` | Split `_aggregate_and_shade` → `aggregate_element` (no shade) + `shade_aggregate(agg, *, palette, continuous_palette, how, title) → (rgba, Legend)`. Add the `agg` reducer map ([D49]). `rasterize_*` become thin: aggregate + default-palette shade, preserving today's return for non-themed callers. | medium |
| `core/encoding.py` | `Legend` is reused as-is. Optionally host a small `category_colors(categories, palette) → (key_dict, entries)` helper so the categorical key + `Legend.entries` share one source of truth (also used by native categorical). | low |
| `core/raster.py` | `RasterController` gains an injected `shade` + an `on_legend` callback (mirrors `rasterize`/`on_aggregate`). Stays theme-free. | medium |
| `backends/*/_renderers.py` | `render_image`, on a datashaded Image, shades from the carried aggregate with `ctx.theme` and draws the legend via the existing `add_legend`/`_add_legend`; passes the themed `shade` + `on_legend` into the controller. | medium |
| `backends/*/_legend.py` (+ mpl `_add_legend`) | Handle **re-draw on re-aggregation** — continuous vmin/vmax change on zoom, so the legend must *replace*, not stack (pyqtgraph `addLegend` would duplicate). | medium |
| `elements/scatter.py`, `elements/curve.py` | Add `agg: AggSpec = "auto"` ([D49]); validate via the `core/_validate` taxonomy (value aggs require `color_by`). | low |
| `data/pipeline.py` | `_rasterize` carries the new `Aggregate` (xarray) on the Image next to `_raster_aggregate`; still bakes a default-palette rgba so nothing downstream regresses. | low |
| `backends/webengine/_figure.py` | One-shot themed `shade_aggregate` in the image path → theme colors + legend without a controller (no 4b loop on webengine yet). | low |

## 3. Discussion items (recommended; confirm at review)

### [D47] Where datashader shading happens, and how the theme reaches it

**Context.** Shading is hard-coded in the pipeline (`tf.shade` with `_VIRIDIS`/
`_CATEGORY10`), theme-less and legend-less ([D20] tension).

**Decision.** Split **aggregate (theme-free, pipeline/controller) from shade
(theme-aware, render-time)**; inject `shade` into `RasterController` exactly as
`rasterize` is injected today, so `core/` gains no theme dependency. Carry the raw
xarray aggregate on the Image so `shade_aggregate` re-shades faithfully via
`tf.shade` rather than re-implementing `eq_hist`/blend in numpy. The pure-numpy
`RasterAggregate` ([D46] hover) is untouched. The pipeline still bakes a
default-palette rgba so non-themed/eager consumers (and webengine pre-W) never
regress; native backends replace it on the controller's first pass (already
immediate today), webengine re-shades once at render.

**Alternatives weighed.** (a) Re-implement shading in numpy inside `core/encoding`
— removes datashader from the shade step and fully unifies native+raster, but
re-deriving `eq_hist`/categorical blend faithfully is error-prone; deferred as a
later "de-datashader the shade step". (b) Thread the theme down into `resolve_node`
— wrong layer; resolve runs before a backend/theme is chosen.

**Enables for free:** `spread`/`dynspread` (a `tf` op in the shade step) — wire the
element flag later, no new seam.

### [D48] Legend honesty for `eq_hist` density vs. value aggregations

**Context.** `count` density shades with `how="eq_hist"` (histogram equalization) —
non-linear, so a linear colorbar with numeric ticks would lie.

**Decision.**
- **Density (`count`)** → keep `eq_hist` (best visual); legend is a ramp keyed
  **"low → high"** with the count range shown but **no linear interior ticks**
  (`Legend` kind `continuous`, ticks suppressed via a flag, or labeled min/max
  only).
- **Value aggregations (`mean`/`sum`/`max`/`min`/`std`)** → default `how="linear"`
  so the colorbar's `vmin`/`vmax` are truthful; `eq_hist`/`log` remain opt-in.
- **Categorical (`by`)** → key legend (category → swatch), identical to native
  categorical.

This couples the default `how` to the agg kind — a small honesty rule, overridable.

### [D49] Aggregation-surface API — vocabulary, default, element field

**Context.** Reductions are implicit today (no `color_by`→`count`; numeric→`mean`;
categorical→`by(count)`), with no way to ask for `max`/`sum`/etc.

**Decision.** Add `agg` to `Scatter` (and `Curve` where meaningful):

```python
AggSpec = Literal["auto", "count", "sum", "mean", "max", "min", "std", "any", "by"]
agg: AggSpec = "auto"
```

- `"auto"` = today's behavior (back-compatible default): no `color_by`→`count`,
  numeric `color_by`→`mean`, categorical `color_by`→`by`.
- `sum/mean/max/min/std` **require** `color_by` (validated via `core/_validate`,
  clear error otherwise). Mapped to `ds.sum/mean/max/min/std(col)`.
- `count`/`any` ignore `color_by`; `by` forces the categorical blend.
- The aggregate's `kind` generalizes from `count|mean|category` to carry the agg
  name (drives the hover label + default legend title).

**Deferred:** multi-agg `summary` (multiple planes → forks shading/legend).

### [D50] Theme palette source for the raster

**Context.** Which palette colors the key/ramp?

**Decision.** Match the native `Scatter` `color_by` path exactly: categorical key
cycles `ctx.theme.palette`; continuous ramp uses the same continuous palette the
native renderers pass (`palettes.get("viridis")` today — or a theme-configured
continuous palette when that lands). Category→color assignment is shared with
native categorical via one `category_colors` helper, so a category gets the **same**
swatch whether drawn as points or as a raster blend.

## 4. Phased plan (sub-milestones)

Ordered so each step is independently reviewable and green (workflow cadence):

- **C1 — Aggregate/shade split (no behavior change).** Refactor
  `_aggregate_and_shade` into `aggregate_element` + `shade_aggregate`; `rasterize_*`
  keep current output (default palette). Pure-numpy `RasterAggregate` unchanged.
  *Tier-1 tests prove identical rgba/bounds/aggregate to pre-refactor.* **[D47]**
- **C2 — Theme-driven colors.** Backends shade the carried aggregate with
  `ctx.theme`; controller gains injected `shade`. Datashaded colors now match a
  non-default theme. **[D50]**
- **C3 — Legends/colorbars.** `shade_aggregate` emits a `Legend`; backends draw it
  via the existing legend path; handle replace-on-re-aggregation. Density-key vs
  value-colorbar honesty. **[D48]**
- **C4 — Aggregation surface.** `agg` field + reducer map + validation; hover label
  + legend title generalize. **[D49]**
- **C5 — webengine parity.** One-shot themed shade + legend in `_figure.py`.

C1 is a pure refactor (safety net first); C2–C4 each add one user-visible
capability; C5 extends to the third backend.

## 5. Benchmarks (per cadence — establish before/after)

Big-data path, so measure the cost the seam adds, not just correctness.

**Measured** (1200×800 raster, shade time only — `aggregate` is unchanged from
before this milestone; numbers independent of row count, as expected for a
raster-size-bound op; 10M-row source):

| agg kind | shade + legend | how |
|----------|----------------|-----|
| `count` density | ~37 ms | eq_hist |
| `mean` / value | ~26 ms | linear |
| categorical blend | ~100 ms | per-category composite |

The original **"< 5 ms" target was wrong** — `tf.shade` itself (eq_hist
equalization, per-category alpha compositing) is the cost, not the legend assembly
(<1 ms). What makes this acceptable is *where* it runs, not how fast:

- **Re-aggregation shade is off the GUI thread.** `themed_rasterize` does
  aggregate+shade together inside the injected `rasterize`, which the
  `RasterController` runs on its worker pool — so the ~26–100 ms never blocks the UI
  during pan/zoom. Verified unchanged: `test_raster_dynamic` (debounce + stale-drop)
  still green.
- **One GUI-thread shade at first paint** — `render_image` shades the initial raster
  with the theme synchronously (one-time, avoids a default-color flash). A known
  follow-up: the pipeline also bakes a default-palette rgba that the themed backends
  immediately re-shade (double work at startup) — droppable once every raster
  consumer re-shades from the carried `Aggregate`.
- **Aggregate memory** — carrying the xarray `agg` (+ categorical per-category
  planes) scales with raster size (w×h×cats), independent of row count.

A `benchmark`-marked test of the shade step is a follow-up; numbers above are from a
manual run on the dev machine.

## 6. Test plan (TDD — write first)

**Tier-1 (pure, no Qt):**
- `shade_aggregate`: categorical aggregate → `color_key` + `Legend.entries` match the
  given palette and category order; continuous → ramp + truthful `vmin`/`vmax`;
  density → "low→high" legend per [D48].
- agg reducer map: each `AggSpec` → correct `ds` reducer; `max`/`min`/`sum`/`std`
  correctness on a known small frame (max-per-pixel value lands in the right cell).
- theme propagation: a non-default `Theme.palette` changes both the rgba **and** the
  `Legend` swatches; category→color is stable across native vs raster.
- validation: a value agg without `color_by` raises the `_validate` error type;
  `agg="auto"` reproduces current behavior byte-for-byte (C1 regression guard).

**Tier-2 (offscreen render, both native backends):**
- datashaded `Scatter(color_by=<category>)` draws a category legend; `<numeric>` with
  `agg="mean"` draws a colorbar; `count` draws a density key.
- re-aggregation on zoom updates a continuous legend's `vmin`/`vmax` and does **not**
  stack duplicate legend items.
- hover value ([D46]) still correct after the split (no regression in
  `test_raster_inspect`).

**Tier-3 (webengine):** themed colors + legend present on a datashaded Image (C5).

## 7. Risks

| # | Risk | Mitigation |
|---|------|------------|
| 1 | Legend redraw on re-aggregation stacks/leaks items (pyqtgraph `addLegend`) | Replace-not-append; track the legend item on the ViewBox like `_qtviz_rasters`; test for single legend after N zooms |
| 2 | C1 refactor silently changes shaded output | Golden-rgba Tier-1 test pins pre/post equality before any behavior change |
| 3 | Carrying the xarray `agg` across the worker-pool thread boundary | It's already-materialized + small (raster-sized); covered by the memory benchmark |
| 4 | `agg` field interacts with auto-routing/`scale` validation | Validate the `(scale, agg, color_by)` triple together in `_validate`; `auto` stays the default |
| 5 | `eq_hist` legend honesty confuses users either way | [D48] explicit policy + doc note; value aggs default to linear `how` |

## 8. Acceptance

A datashaded categorical `Scatter` over a 10M-row dask source renders, on pyqtgraph
**and** matplotlib, with: (a) colors from `Theme.dark()` (not the fixed default),
(b) a category legend that matches a native `Scatter` of the same column, and (c) a
truthful colorbar when switched to `agg="mean"`. Pan/zoom keeps the legend correct
and un-duplicated. Out-of-core and hover ([D46]) are preserved. ≤ the
`milestone-phase4-datashader.md` LOC budget for the new seam.
