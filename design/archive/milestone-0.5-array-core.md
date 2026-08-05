# Milestone — 0.5 "The array data core" (owner-directed scope)

> The 0.5 slot in `improvement-plan.md` re-scoped by owner direction
> (2026-07-24): **deepen the array-container data layer** — numpy, pandas,
> dask, zarr, xarray — rather than build the Parquet/DuckDB/SQL file-source
> layer (which stays parked with datetime axes, [D62]). Decisions
> **[D73]–[D75]** below.
>
> The driving defect: every **lazy gridded** ref fully materializes to render —
> `ZarrGriddedRef.materialize` is literally `self._z[:]`; dask/xarray grids
> `.compute()` whole. A 10 GB zarr loads 10 GB to paint 800×600 px. The
> "engineered for large data" claim (README) is true for *points* (datashader)
> and false for *grids*. 0.5 makes it true for grids.

## 0. Goal & scope

**Goal.** A huge gridded array (zarr / dask / N-D xarray) renders at **screen
cost, not array cost** — reading only ~viewport×resolution cells, sharpening on
zoom exactly like the datashaded point path — and each of the five focus
containers wraps with less friction.

**In scope.**
- **[D73] Container ergonomics:** pandas index → column; `zarr.Group` →
  tabular; `gridded()` on a one-var xarray `Dataset`; cheap coord-based extents.
- **[D74] Decimated gridded materialize:** `materialize(max_cells=…)` — strided,
  chunk-friendly decimation on the three lazy gridded refs; the resolve pipeline
  budgets lazy grids at the raster size instead of computing them whole.
- **[D75] Viewport regrid:** `window()` on lazy gridded refs + the existing
  `RasterController` re-reading the visible window at widget resolution on
  pan/zoom (both native backends), with a theme-shaded raster + colorbar that
  refreshes — full parity with the datashaded Scatter experience.

**Deferred / non-goals.** Parquet/DuckDB/SQL sources + query cache (parked with
[D62]); datetime dtype (parked); mean-downsampling via datashader
`canvas.raster` (strided decimation first — the seam accepts a better kernel
later); webengine dynamic regrid (static decimated render only — the JS bridge
has no viewport loop today); `qtviz.data_adapters` entry-point (ecosystem,
parked with the private-repo ruling).

---

## 1. Container ergonomics ([D73])

| Container | Today | 0.5 |
|---|---|---|
| **pandas** | the index is dropped — a time-indexed frame needs `reset_index()` to plot | the index joins the columns as `index.name or "index"` (a real column name never collides: data columns win, with a one-time warning) |
| **zarr** | `zarr.Group` matches the adapter but breaks on `.shape` | a Group of 1-D arrays → **tabular** (members = columns, validated equal lengths); nested/N-D members → clear `AdapterError`; `zarr.Array` unchanged (gridded) |
| **xarray** | `gridded(Dataset)` raises always | a **single-var** Dataset → that var's `XarrayGriddedRef`; multi-var → error naming the variables (pick one: `ds["temp"]`) |
| **xarray extents** | `extent()` → None | gridded `extent(dim)` from the (small, eager) coord arrays — no compute; tabular Dataset likewise for coords |
| **numpy / dask / arrow** | fine | unchanged (numpy 2-D→tabular stays rejected — no invented column names) |

## 2. Decimated materialize ([D74])

- `GriddedRef.materialize(max_cells: int | None = None)` — when the array
  exceeds `max_cells`, slice with per-axis strides before reading
  (`z[::sy, ::sx]`); coords decimate with the same stride so bounds stay
  exact. `None` (default) keeps today's full read — the *pipeline* chooses
  the budget, the ref just obeys.
- **What decimation buys (spiked, honest):** the materialized result is
  *memory-bounded* (~budget cells instead of the full array — the OOM killer),
  and chunks are *skipped* only when the stride exceeds the chunk extent
  (counting-store test pins both). Sub-chunk strides still decode every chunk;
  strictly-partial I/O comes from `window()` (§3), which reads only in-window
  chunks (spiked: 1 of 256).
- The resolve pipeline materializes a lazy gridded element at
  `4 × _RASTER_SIZE` cells (headroom above widget resolution; `set_raster_size`
  scales it). Small arrays under budget are untouched — zero behavior change.
- Decimation is resolution management, not option-dropping — no warning
  (same policy as datashader's `scale="auto"`), documented on the ref.
- The lazy ref is stashed on the resolved element (`_grid_source`, mirroring
  the datashader `_raster_source` pattern — private, excluded from value
  identity) so the renderer can wire the dynamic loop (§3).

## 3. Viewport regrid ([D75])

- `window(x=(lo,hi), y=(lo,hi))` on `ZarrGriddedRef` / `DaskGriddedRef` /
  `XarrayGriddedRef`: slice the 2-D array to the coordinate window (xarray by
  coords; zarr/dask by index mapped through bounds) and return a narrowed lazy
  ref. Never a dead field: §3 wires its only caller in the same increment.
- `data/regrid.py`: `regrid(ref, *, width, height, x_range, y_range) →
  RegridResult(rgba, bounds, aggregate, legend)` — window → decimate to
  (width, height) → shade values through the shared viridis ramp
  (`map_colors`) with a truthful colorbar `Legend` (vmin/vmax of the visible
  window — refreshes on zoom like the datashader value path, C3).
- Renderers (pyqtgraph + matplotlib): an `Image` carrying `_grid_source` is
  drawn shaded (same ramp as the dynamic loop — no first-tick flicker) and
  wired to a `RasterController` with the regrid function — the *same*
  controller, targets, debounce, off-thread pool, and stale-drop the
  datashader path uses. Disposal through the existing `_qtviz_rasters` hooks.
- webengine renders the static decimated raster (no viewport loop — noted gap).

## 4. Discussion items (recommended; confirm at review)

### [D73] Ergonomics cut
Index-as-column, zarr Groups, one-var Dataset gridding, coord extents — and
*nothing else* (no invented 2-D-numpy column names, no multi-var pivoting).
*Alternative:* leave ergonomics to user preprocessing (rejected: the pandas
index case hits every time-indexed frame, the most common real container).

### [D74] Strided decimation, budget = 4× raster size, silent
*Alternatives:* datashader `canvas.raster` mean-downsampling (better
anti-aliasing, heavier dep path — the `materialize(max_cells)` seam accepts it
later); warn on decimation (rejected — it's resolution management, like
datashader auto-routing, not a dropped option).

### [D75] Reuse RasterController wholesale
The gridded loop is the datashader loop with a different `rasterize` — same
debounce/off-thread/stale-drop/legend-refresh semantics, same per-backend
targets. *Alternative:* a separate GridController (rejected: duplicate
machinery, drift risk).

## 5. Test plan (TDD — write first)

**Tier-1 (pure):** pandas index column (named/unnamed/collision-warns); zarr
Group tabular + mismatched-length + N-D member errors; one-var Dataset gridding
+ multi-var error; coord extents; decimated materialize shapes/strides/coord
alignment (and `max_cells=None` unchanged); **partial-read proof** — a counting
zarr store asserts decimation touches a small fraction of chunks and `window`
touches only in-window chunks; `regrid` windows+shades with truthful legend
bounds; `window()` narrowing on all three lazy refs.

**Tier-2 (offscreen, both native backends):** a large (memory-store) zarr
Image renders decimated (item pixel size ≤ budget) with a colorbar; zoom via
`setXRange` → controller re-reads the window (waitUntil the image narrows);
dispose tears the controller down; xarray dask-backed grid same path; small
eager grids render exactly as before (regression).

## 6. Benchmarks (per cadence)
`test_bench_regrid.py`: decimated vs full materialize on a 8k×8k memory-store
zarr (decimated must be ≥10× faster and bounded by budget); `regrid` per-call
cost at widget resolution (ms-scale — it sits on the zoom path).

## 7. Phased increments (review at each boundary)
1. **Ergonomics ([D73])** — pandas index, zarr Group, Dataset gridding, extents.
2. **Decimated materialize ([D74])** — `max_cells` on the three refs + pipeline
   budget + `_grid_source` stash + partial-read tier-1 proof.
3. **Viewport regrid ([D75])** — `window()` + `regrid()` + both native
   renderers wired through `RasterController`; shaded static render for
   consistency.
4. **Benchmarks + acceptance + CHANGELOG.**

## 8. Risks
| # | Risk | Mitigation |
|---|---|---|
| 1 | Strided zarr reads still touch many chunks when strides ≪ chunk size | stride reads are contiguous per chunk row; the counting-store test pins the read fraction; `canvas.raster` upgrade path documented |
| 2 | Shading the dynamic path changes the static look of lazy grids | static render of `_grid_source` images shades with the same ramp (§3) — consistent from the first frame |
| 3 | Coord-space `window` on index-only zarr/dask grids | bounds map through the decimated coords (linear index↔coord); tested round-trip |
| 4 | Regrid loop fights the datashader loop on the same ViewBox | mutually exclusive by construction: `_raster_source` (points) vs `_grid_source` (grids) never co-exist on one Image |
| 5 | Behavior change for big-grid users | only above budget (was: full compute, often OOM); under budget unchanged; CHANGELOG calls it out |

## 9. Acceptance
A 16k×16k zarr array (memory store) — 256M cells — shows up in a `View` in
milliseconds, having read a small fraction of its chunks (counting store
asserts it); pan/zoom re-reads only the visible window at widget resolution and
the image *sharpens*; the colorbar tracks the visible value range; a dask-backed
xarray field takes the same path; `examples/29_climate_field.py` still renders
identically (under-budget regression). Suite green; ruff clean; benchmarks
within ceilings.
