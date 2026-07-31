# Changelog

All notable changes to qtviz are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Parity program ([`design/parity-program.md`](design/parity-program.md)) — the
post-1.0 arc growing the vocabulary and axes toward "the everyday figures of
the popular libraries, declaratively" ([D83]).

### Added

- **`Contour` ([D89]).** Iso-value contours over a 2-D grid (the `Image`
  data contract): `levels` (count or explicit values — computed once in core
  so every backend draws the same lines), `filled`, `colormap`,
  `line_width`. matplotlib `contour/contourf` (+ colorbar when filled),
  Plotly `contour` traces, pyqtgraph `IsocurveItem` per level mapped onto
  `bounds` (`filled` warns there — no pg primitive). Contour surfaces join
  the raster force-linear scale gate.
- **Three new elements ([D84b]/[D90]/[D91]).** `Area` — zero-baseline filled
  series; with `group=` one palette band per category, layered
  (`mode="overlay"`) or cumulatively stacked (the [D68] grouping pattern) —
  all three backends. `Ecdf` — the empirical CDF of a column, computed in
  core ([D67] shared numbers) and drawn as a post-step curve — all three
  backends. `Pie` — proportional wedges with optional `labels` and a `hole`
  for donuts — matplotlib + webengine; pyqtgraph has no pie primitive, so
  negotiation routes around it (the `RawFigure` precedent).
- **Step curves and curve markers ([D84]).** `Curve(step="pre"|"mid"|"post")`
  renders stepped lines and `Curve(marker=...)` puts point symbols on the line
  (the 5-marker vocabulary), on all three backends.
- **Horizontal bars wired ([D85]).** `Bars(orient="h")` — simple, grouped and
  stacked — now renders horizontally on matplotlib and pyqtgraph (it
  warned-and-degraded) and on webengine grouped bars (simple bars already
  worked); categorical tick labels move to the y axis.
- **Surface grid toggle ([D87]).** `OverlayOptions(grid=False)` turns the
  grid off on every backend (it was permanently on).
- **Twin y axes ([D88]).** `Curve`/`Scatter` gain `axis="y2"`; the surface
  gains `OverlayOptions(y2=AxisSpec(...))` to configure the right-hand axis
  that appears when any child asks for it (label, scale, lim, invert,
  tick_format all honored). matplotlib `twinx`, pyqtgraph x-linked twin
  `ViewBox` driven by the right `AxisItem`, Plotly `yaxis2`. `ViewState`
  grows an additive `y2_range` so twin ranges survive rebuilds and backend
  switches; events stay primary-axes (y2 elements are not brush-selectable —
  documented). `axis="y2"` with `scale="datashader"` raises.
- **Tick formatting wired ([D86]).** `AxisSpec(tick_format=…)` — reserved
  since 0.3 — now formats ticks on all three backends: a Python format-spec
  string (`".2f"`, `",d"`, `".0%"`, …) or `"eng"` (SI prefixes). matplotlib
  gets a `FuncFormatter`, pyqtgraph a data-space `tickStrings` override
  (labels read 10**v under log — R1), webengine the d3-format twin. Invalid
  specs raise `ValidationError` at construction.
- `Bars.mode` joined the honor-or-warn contract (`RECOMMENDED_OPTIONS`), and
  `Bars(mode="stacked")` without `group=` is now a `ValidationError` instead
  of a silent no-op.
- **Colormaps wired beyond matplotlib ([D92]).** `Image.colormap` and
  `Heatmap.colormap` are honored on pyqtgraph (pg's maps, then matplotlib's
  registry, warn-fallback to viridis) and webengine (named Plotly colorscales,
  warn-fallback to Viridis); `Image.interpolation` maps to Plotly `zsmooth`.
- **pyqtgraph `ErrorBars` honors `color` and `direction`** (x / y / both,
  with the log-space delta treatment on both axes).

### Changed

- **One histogram binning engine ([D93]).** `Histogram` is binned once in
  core (`np.histogram`) and every backend draws those bars — previously
  numpy, `Axes.hist` and Plotly each binned their own way, so the same
  Element drew different charts per backend. numpy rule strings
  (`"fd"`, `"sturges"`, …) now pass through instead of collapsing to
  `"auto"`; unknown rules and non-positive counts raise `ValidationError`.
  webengine emits a pre-binned `bar` trace instead of a `histogram` trace.
- **`Heatmap` renders in real data coordinates ([D92]).** matplotlib and
  pyqtgraph now place cells at the x/y values (categorical axes get index
  positions + tick labels), matching webengine; pyqtgraph heatmaps were
  additionally **transposed** (col-major default) relative to the other
  backends — fixed with row-major orientation.

### Fixed

Three silent-drop warts surfaced by the matplotlib support audit
(`design/matplotlib-support-matrix.md` §11):

- **`Scatter(matplotlib_rasterized=True)` now reaches the artist.** The
  backend-prefixed flag was stored but read by no renderer; the matplotlib
  scatter now passes it through, so large point clouds can rasterize inside
  SVG/PDF exports. (`pyqtgraph_use_opengl`, its sibling, remains unwired —
  tracked as an open wire-or-deprecate decision.)
- **`OverlayOptions(background=…)` is honored on all three backends.** It was
  defined but consumed nowhere; it now sets the *plot area* (matplotlib axes
  facecolor, pyqtgraph `ViewBox` background, Plotly `plot_bgcolor`) while the
  figure/widget chrome stays on the `Theme`.
- **`ErrorBars(direction="both")` draws both whisker sets.** matplotlib
  emitted y-error only and webengine had the same `error_y`-only bug; both
  now emit x *and* y errors, and `direction="x"` still draws x only.

## [1.0.0] — 2026-07-24

The stability release. The 0.3–0.6 milestones below were developed against the
staged post-0.1 program (`design/improvement-plan.md`) and were never tagged
individually — 1.0.0 ships them together, under a frozen, policy-backed public
surface.

### The 1.0 promise

- **API freeze.** `qtviz.__all__` is a contract, pinned exactly by the suite
  (`test_api_freeze.py`); the stability & deprecation policy is documented
  (`docs/stability.md`): semver, warn ≥2 minor releases before removal, what
  is public and what never was.
- **Removed:** the `qtwebplot` import shim (deprecated 0.1, promised for two
  releases, kept for five). `qtviz.Options` still warns — 0.2 promised it
  "importable through 1.0", so 1.1 removes it.
- **Quality gates, local by design** (the owner removed CI deliberately):
  mypy over `src/qtviz` at zero errors; coverage measured 90% with an 88%
  floor; the full gate list is a release step in `RELEASING.md`.
- **Docs:** the extensibility story ships — "writing a backend"
  (`docs/backends.md`) with the three honesty contracts and a worked example;
  README describes 1.0, not "toward 0.1".
- Typing hardening along the way: the gridded `window()` signature now matches
  the `DataRef` contract (LSP-clean `**ranges`).

### 0.6 — Live & linked

Live & linked ([D63] — the differentiator; `design/milestone-0.6-live.md`,
[D76]–[D78], resolves the long-open [D7]). Streaming + linked brushing through
a datashaded view, as plain desktop widgets.

#### Added

- **`qv.stream(...)` ([D76]).** A mutable, append-able tabular `DataRef` with
  ring-buffer rolling windows (`window=` — the spec §12 "auto-rolling"
  deferral, lifted). `append(**columns)` from any thread; renders never see a
  torn append; notifies through the base contract's `subscribe` seam —
  designed in Phase 1, dead until now. Elements stay immutable ([D38]/R1).
- **Incremental refresh ([D77]).** `RenderHandle.set_element_data` — pyqtgraph
  updates live Scatter/Curve items in place (`setData`, ms at 100k points; log
  surfaces stay R1-consistent; brush selectables refresh), finally backing the
  `streaming=True` it has declared since 0.1. Appends coalesce to **one
  refresh per event-loop tick** ([D7] resolved); other paths degrade
  explicitly (webengine: Plotly-react diff; matplotlib: debounced rebuild —
  its `streaming=False` was always honest). A user zoom is never re-ranged.
- **Raster selection ([D78]).** Brushing a datashaded view (which emitted
  nothing) now emits a `SelectEvent` for the *source* element: true row
  indices when the source is eager (closing the [D58] pixel→source-rows
  deferral), and bounds-only for lazy sources — the predicate that scales,
  filtered downstream via `window(bounds)` pushdown. Both native backends;
  crossfilter-through-a-raster works end to end.
- `examples/34_streaming_telemetry.py` — the milestone dashboard: a live
  rolling feed, a datashaded 400k history, and a raster brush driving a
  linked detail panel via signals, in ~90 lines.

### 0.5 — The array data core

The array data core (owner-directed scope: numpy / pandas / dask / zarr /
xarray; `design/milestone-0.5-array-core.md`, [D73]–[D75]). Huge gridded
arrays now render at **screen cost, not array cost**.

#### Added

- **Decimated gridded materialize ([D74]).** A lazy grid (zarr / dask / N-D
  xarray) over budget reads a strided, screen-scale slice instead of
  computing whole (`ZarrGriddedRef.materialize` was literally `z[:]` — a
  10 GB array to paint 800×600 px). Memory-bounded at ~4× the raster size;
  coords decimate with the data so geometry stays exact; under-budget arrays
  are untouched.
- **Viewport regrid ([D75]).** `window()` on the lazy gridded refs
  (strictly-partial chunk I/O — a chunk-sized window reads 1 chunk of 64) +
  a regrid loop through the same `RasterController` as the datashader path:
  pan/zoom re-reads only the visible window at widget resolution and the
  image *sharpens*; the raster is shaded through the shared encoding ramp
  with a colorbar that tracks the visible value range. Both native backends;
  webengine renders the static decimated raster.
- **Container ergonomics ([D73]).** The pandas index joins the columns
  (time-indexed frames plot without `reset_index()`; a real column wins a
  name collision with a warning); a `zarr.Group` of 1-D arrays is a table;
  `gridded()` on a single-variable xarray `Dataset` selects the variable;
  xarray grid extents come from the eager coord arrays without computing.

### 0.4 — Vocabulary, annotation & export

Vocabulary, annotation & export (R2/R3 partial + R6;
`design/milestone-0.4-vocabulary.md`, [D67]–[D72]). Everything additive; the
vocabulary stays curated ([D54]).

#### Added

- **Annotation/reference elements ([D70]).** `HLine` / `VLine` / `Span` /
  `Text` — data-less pure-data elements, composable via `*`, on all three
  backends (webengine renders them as Plotly layout shapes/annotations).
  Default to the theme foreground (chrome, not a palette series); a labeled
  reference joins the legend; positions follow the axis scale (R1).
- **Grouped / stacked Bars ([D68]).** `Bars(group=…, mode="grouped"|"stacked")`
  — one palette-colored series per group (category order = the `color_by`
  rule) with a group legend, identical numbers on every backend via the shared
  `group_bars` helper. `group` is finally honored, everywhere.
- **A real `Heatmap.aggregator` ([D69]).** `mean|sum|count|max|min|last`
  actually reduces duplicate cells (shared `grid_reduce`); closes the
  "last value wins" TODOs. Default is `mean` — the old implicit `last` stays
  in the vocabulary.
- **BoxPlot + Violin ([D67]).** One stats core (`box_stats`: linear-interp
  quartiles, 1.5·IQR whiskers clipped to data, outliers; `kde`: Gaussian,
  Scott's rule) shared by all three backends — webengine gets *precomputed*
  box traces and polygon violins, never Plotly's house statistics. `by=`
  splits per category with palette colors + legend.
- **Log color normalization ([D71]).** `Scatter(color_by=…, color_norm="log")`
  maps colors through log10 on every backend; the legend is an endpoints-only
  key ([D48] honesty — never a linear gradient bar over a log mapping).
- **Composite export ([D72]).** A mixed-backend `Layout` exports one PNG
  (`handle.export("png", …)` grabs the whole Qt container) instead of
  raising; vector formats stay per-pane by design ([D58]). Export knobs
  `dpi` / `transparent` — honored by matplotlib, honored-or-warned elsewhere.

#### Fixed

- **Native series colors now cycle the palette.** Multiple default-colored
  series in an Overlay drew identically (all `palette[0]`) on the native
  backends while webengine cycled — and legend swatches disagreed with the
  drawn colors. One `series_index_map` now drives default colors and legend
  swatches on all three backends; annotation elements don't consume slots.

### 0.3 — First-class axes & legends

First-class axes + legends (root cause R5; `design/milestone-0.3-firstclass.md`,
[D59]/[D60]). The two afterthoughts promoted to real models.

#### Added

- **First-class axes ([D59]).** `qv.AxisSpec` (`label` / `scale` / `lim` /
  `invert`) on `OverlayOptions.x`/`.y` + `aspect`. `scale="log"` renders on
  **all three backends** — with every coordinate crossing the seam (events,
  brush bounds, capture/restore, backend switches) normalized to **data
  space**, never log space. `symlog` renders on matplotlib and warns→linear
  elsewhere (`Capabilities.scales` gating); non-positive values under log
  drop with a one-time `QtvizWarning`; rasters (Image/Heatmap/datashaded)
  under a non-linear scale warn and render linear. Declarative `lim` sets the
  initial range; a live pan/zoom (`ViewState`) wins across rebuilds.
- **Legend contract ([D60]).** A `label` field on the styling elements
  (Scatter/Curve/Bars/Histogram/ErrorBars/Spread) + `Element.legend_entry()`;
  an Overlay aggregates contributions into **one** legend, merged with any
  `color_by` color-mapping legend (no double legends — a `color_by` Scatter
  opts out of the contract). The previously-dead `OverlayOptions.legend` now
  works, joined by `legend_position` (`auto|right|top|none`); `legend=False`
  silences every legend path, including raster re-aggregation refreshes.
- **Legend parity ([D55]).** webengine finally draws legends (`showlegend`
  follows the surface; traces opt in per-label) and a true Plotly colorbar for
  continuous `color_by`; pyqtgraph's 5-stop stepped swatch is replaced by a
  true gradient `pg.ColorBarItem` (eq_hist density honestly keeps its
  endpoints-only key, [D48]).
- Docs drift guard: every `qtviz.__all__` name must appear in `docs/api.md`
  (tier-1 test, improvement-plan [D65]).

## [0.2.0] — 2026-06-18

Hardening pass from the post-0.1 weakness investigation (root causes R1–R6;
`design/weakness-root-causes.md`). No new chart types — the existing surface made
**honest**, plus a native escape valve.

### Fixed

- **Silent option drops are gone (§3.4 honor-or-warn, [D51]).** An option a backend
  doesn't support no longer vanishes silently — it warns once (`QtvizWarning`) and
  rendering proceeds. Newly *honored* (were dropped): `Scatter.marker` (all backends),
  `Scatter.alpha` and `Curve.line_style`/`alpha` (pyqtgraph), `Image.interpolation`
  (matplotlib). A backend-conformance test now guarantees every recommended option is
  honored-or-warned, so silent drops can't return.

### Changed

- **Honest capabilities ([D52]).** matplotlib and webengine no longer advertise
  `dimensions={2,3}` or `animation` — there is no 3-D renderer or animation API yet;
  both are corrected, and a conformance test guards against aspirational flags.

### Added

- **`View.native(element_id)` / `RenderHandle.native(element_id)`** — the escape
  valve ([D53]) to the live backend primitive (pyqtgraph `PlotItem`, matplotlib
  `Artist`/`Axes`, or the webengine figure host) for backend-native interaction the
  typed events don't expose: ROIs, crosshairs, region selectors, native signals.
  Non-portable by design; the live object is returned *through the handle*, never
  stored on the immutable Element, so the purity invariant holds. Rebuilds on
  `update()`. Composite (mixed-backend) handles fan out across panes.
- `qtviz.errors.QtvizWarning` — a filterable category for non-fatal degradation notices.

### Deprecated

- **`qtviz.Options`** — unused (per-element styling lives on the elements themselves);
  constructing it now warns (`DeprecationWarning`). Removed after 1.0.

## [0.1.0] — 2026-06-18

First public pre-release. One immutable `Element` API rendered across three
backends, a lazy-first data layer, and a big-data path — all 100% offline.

### Added

- **Core model** — immutable, value-hashed `Element` (Scatter, Curve, Bars,
  Histogram, Image, Heatmap, ErrorBars, Spread) plus `RawFigure` passthrough;
  `Overlay` (`*`) and `Layout` (`+`: grid / splitter / tabs / dock) composition;
  a typed event bus (`Range` / `Pick` / `Select` / `Hover` / `Tap`).
- **Backends** — pyqtgraph (native, default, OpenGL), matplotlib (vector export),
  and webengine (Plotly in a `QWebEngineView`, plus `RawFigure` hosting for
  Plotly / Bokeh / HoloViews). Registered, never imported by the core; runtime
  backend switching; mixed-backend layouts with one merged event stream.
- **Data layer** — container-agnostic, lazy-first accessors (column / `Expression` /
  callable / array) over dict / NumPy / pandas / Arrow (eager) and Dask / xarray /
  zarr (out-of-core, off the GUI thread); `tabular()` / `gridded()` shape overrides.
- **Encoding** — `color_by` / `size_by` with automatic legends and colorbars.
- **Datashader** — `Scatter` / `Curve` with `scale="datashader" | "auto"`: density,
  `color_by` mean, categorical blend; out-of-core, backend-agnostic, re-aggregating
  to the viewport on zoom. Hover a raster for the aggregated value
  (`HoverEvent.value`). Datashaded rasters now carry a **legend / colorbar**, take
  their **colors from the View's `Theme`** (matching a native `color_by`), and expose
  a wider **aggregation surface** via `Scatter.agg`
  (`count`/`sum`/`mean`/`max`/`min`/`std`/`any`/`by`) — built on an aggregate/shade
  split ([D47]–[D50]). Density keeps an honest endpoints-only key under `eq_hist`;
  value aggregations show a truthful linear colorbar.
- **Reactive** — S-style `signal` / `derived` / `effect` / `batch`;
  `View(Signal[Node])` re-renders on change; crossfilter / linked brushing without
  manual wiring.
- **HoloViews / hvplot adapter** — `from_holoviews(obj)` translates a HoloViews tree
  to native Elements (`RawFigure` fallback for the long tail); `DynamicMap` →
  `Signal[Node]` one-way re-render (`from_holoviews_dmap`); `from_hvplot(df, kind, …)`
  one-liner.
- **Offline guarantee** — no network at render time; the webengine backend bundles
  its JavaScript from the installed packages, never a CDN.
- **Export** — PNG (pyqtgraph), PNG / SVG / PDF (matplotlib), PNG (webengine).
- **Validation contract** — bad constructor input (out-of-range opacity,
  mutually-exclusive channel pairs, unknown column) raises
  `qtviz.errors.ValidationError`, which subclasses **both** `QtvizError` and the
  stdlib `ValueError`; `except QtvizError` now catches every deliberate rejection,
  including construction errors, while `except ValueError` keeps working. Mutable
  setters validate eagerly: `set_default_backend` rejects an unregistered name,
  and `set_raster_threshold` / `set_raster_size` reject non-positive values. Every
  `data=` parameter is annotated `DataLike`.
- `qtviz.__version__`.

### Notes

- `qtwebplot` was renamed to qtviz; `import qtwebplot` keeps working through a
  deprecation shim (redirects to `qtviz.backends.webengine`) for two releases.
- Not yet published to PyPI; the public API may still change before 1.0.
