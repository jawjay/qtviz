# qtviz — capabilities & gaps register

> A living list of what the library can and cannot yet do, and the specific
> capabilities it needs to acquire for the integrations on the roadmap (reactive
> signals, data sources, the HoloViews adapter, the webengine backend). Written
> alongside the Phase-4 Datashader work [D18–D22]; companion to `roadmap.md` §0
> and `development-plan.md` §8. Each gap notes **why it matters** and **what it
> blocks**, so the next phase can be scoped from this list rather than rediscovered.

## 1. Datashader coverage (Phase 4)

What the big-data path does today, and where it stops.

| Capability | Status | Notes |
|------------|--------|-------|
| Point density (`Scatter`, `count`) | ✅ | backend-agnostic raster, out-of-core, off-thread [D18] |
| Line density (`Curve`, `canvas.line`) | ✅ | 1-px lines; `scale="datashader"/"auto"` |
| Value aggregation (`color_by` numeric → `mean`) | ✅ | continuous shade (viridis) |
| Categorical color (`color_by` category → `by(count)`) | ✅ | per-category blend; default `category10` key |
| Viewport re-aggregation on zoom | ✅ | `RasterController` + per-backend `RasterTarget` [D21] |
| Auto-routing by size / laziness | ✅ | `set_raster_threshold`, lazy/unknown size routes |
| **Legend / colorbar for the raster** | ⬜ | a datashaded plot is a bare image — no key for categories, no scale for the continuous ramp. **Blocks** publishable categorical/continuous plots. |
| **Theme-driven colors** | ⬜ | the color key/ramp is a fixed default, not the `View`'s `Theme`/`Palette`; shading happens in the (theme-less) pipeline [D20 tension]. **Blocks** consistent theming. |
| **Aggregation surface** (`sum`/`max`/`min`/`std`, `by(mean)`, multi-agg `summary`) | ⬜ | only `count`/`mean`/`by(count)` are wired. **Blocks** "max value per pixel" style views. |
| **Line width / antialiasing / categorical lines** | ⬜ | `Curve.line_width`/`line_style`/`color` ignored under datashader; no per-category line color. |
| **Gridded regrid** (`canvas.raster` for huge `Image`/`Heatmap`) | ⬜ | only point/line glyphs; large 2-D arrays aren't downsampled to screen res. |
| **Reverse lookup / inspect** (pixel → aggregated value or source rows) | ⬜ | hover/pick/brush don't resolve through a raster (no per-point identity). **Blocks** linked brushing on datashaded views — see §2 *Interaction*. |
| **`spread`/`dynspread`** for sparse zoomed-in pixels | ⬜ | single-pixel points can disappear when zoomed in. |
| **Log / datetime axes** (datashader `logx`/`logy`) | ⬜ | no axis-transform routing — see §2 *Rendering semantics*. |
| Static `color` under datashader | ⬜ (by design) | `Scatter.color` is ignored when rasterizing; single-hue tinting could be added. |

## 2. Cross-cutting capability gaps (needed for future integration)

Grouped by theme. The right-hand column is the roadmap work each gap gates.

### Rendering semantics
| Gap | Why it matters | Gates |
|-----|----------------|-------|
| **Axis transforms** — log / symlog / datetime scales | real scientific/financial data needs them; also unlocks datashader `logx/logy` | all backends; Datashader §1 |
| **Legends & colorbars** as first-class overlay elements | every `color_by`/categorical/continuous plot is ambiguous without a key | HoloViews adapter, Datashader §1, release |
| **`color_by` / `size_by` in native renderers** | today these are honored only by Datashader; native `Scatter`/`Curve` ignore them (`render_scatter` uses static `color` only) | a shared `ColorMapping` abstraction (below) |
| **Shared color-mapping abstraction** | one resolution of value/category → color, used by *both* native per-point rendering and Datashader shading, theme-aware | native `color_by`, Datashader theming, legends |
| **More elements** — Box/Violin, Contour, Quiver, Graph/Network | analysis parity; HoloViews has these | HoloViews adapter, release breadth |

### Data
| Gap | Why it matters | Gates |
|-----|----------------|-------|
| **`DataSource` protocol** — Parquet / DuckDB / CSV / SQL, lazy + background queries | out-of-core *from disk/db*, not just from an in-memory dask object (which adapters already cover) | roadmap Phase 5 |
| **Query pushdown** — `select`/`window`/predicate → SQL / Arrow filter | only scan what a viewport needs; the lazy `DataRef` contract has the seam, sources must honor it | Phase 5, Datashader at 50M+ |
| **Aggregate / query result caching** (versioned LRU) | re-aggregating the same viewport/window is wasteful; the raster controller recomputes from scratch each zoom | Phase 5, Datashader perf |
| **`qtviz.data_adapters` entry point** | third parties register adapters without editing core (mirrors the backend registry; designed, not wired) | ecosystem |

### Reactivity
| Gap | Why it matters | Gates |
|-----|----------------|-------|
| **`Signal` binding** — a `DataRef`/accessor that wraps a reactive value and re-resolves on change | the async-resolve + accessor machinery is ready; needs the reactive seam (finer than `View.set_root`) | roadmap Phase 4 (reactive) |
| **Linked brushing via signals** | brushing one view filters another without manual wiring; the canonical crossfilter demo | reactive; needs source-row identity through Datashader (§1) |
| **Partial / in-place update** | `RenderHandle.update` exists for pyqtgraph but rebuild is the common path; reactive wants cheap diffs | reactive perf |

### Interaction
| Gap | Why it matters | Gates |
|-----|----------------|-------|
| **Selection model + source-row identity through a raster** | brush/pick on a datashaded view must map pixels back to rows (or to a data-space predicate) | linked brushing, crossfilter |
| **Inspect / hover-value on rasters** | show the aggregated value (count/mean) under the cursor | datashader UX |
| **Viewport → data-window hook for native rendering** | large-but-not-huge data could downsample/window without full Datashader; the `window` primitive exists [D16] but isn't auto-wired | perf, Phase 5 |

### Backends & export
| Gap | Why it matters | Gates |
|-----|----------------|-------|
| **webengine backend** — Element → Plotly/Bokeh traces, Arrow IPC transport, capability declarations | the Backend protocol supports it; the legacy qtwebplot bridge must be rehomed under it | roadmap Phase 5 |
| **HoloViews adapter** — element translation, Overlay/Layout/GridSpace, `DynamicMap`→reactive, `Stream`→event | one-way `from_holoviews()`; depends on legends + the element set above | roadmap Phase 3 |
| **Composite / mixed-backend export** | a `CompositeRenderHandle` raises on `export` — no single surface | release |
| **CI matrix** (macOS/Linux/Windows × 3.11–3.13) | never set up; the only cross-platform guarantee today is local | every phase |

## 3. Prioritized next capabilities

Ordered to unblock the most downstream work per unit effort (ties to
`development-plan.md` §8):

1. **Shared color-mapping + legends/colorbars** — unblocks native `color_by`,
   Datashader theming, and is a prerequisite the HoloViews adapter will need.
2. **Axis transforms (log/datetime)** — broadly needed; cheap relative to value.
3. **Reactive `Signal` binding** — the machinery is in place; highest leverage for
   the crossfilter story (with selection identity, below).
4. **Selection model + raster reverse-lookup** — turns Datashader views into
   first-class interactive citizens; pairs with reactivity for linked brushing.
5. **`DataSource` (Parquet/DuckDB) + query pushdown + caching** — the out-of-core
   *source* layer; also fixes Datashader re-aggregation cost at 50M+ rows.
6. **HoloViews adapter**, then **webengine rehome**, then **release `0.1`**.

This register is expected to churn — close a row when its capability lands, add a
row when a new integration surfaces one.
