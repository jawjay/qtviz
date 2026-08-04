# Changelog

All notable changes to qtviz are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased — 2.0]

The Mark IR + uniform-surface arc
([`design/2.0-mark-ir-and-surface.md`](design/2.0-mark-ir-and-surface.md),
[D121]–[D136]) — a clean 2.0 break: internal waves land first (no public
surface change until the wave-1 renames; the freeze list flips to
`FROZEN_2_0` last).

### Changed (wave 1 — [D129]/[D131] mechanical channel renames, breaking)

One channel-binding convention across all elements: *data first; every data
binding is a keyword **accessor** (`str | Expression | Callable | ArrayLike`,
[D14] — renames change names, never accepted types)*. Pure renames, no
behavior change; examples/tests/docs migrated in the same commits.

| Before | After | Elements |
|---|---|---|
| `column=` | `value=` | Histogram, Ecdf, BoxPlot, Violin |
| `values=` / `labels=` | `value=` / `by=` | Pie |
| `group=` | `by=` | Bars, Area |
| `bounds=` | `extent=` | Image, Contour, Streamlines |
| `x_edges=` / `y_edges=` | `x=` / `y=` | Mesh |
| `scale=` | `raster=` | Scatter, Curve (`scale` now means only axis transform) |
| `bar_labels=` / `cell_labels=` / `labels=` | `annotate=` | Bars, Heatmap, Contour |

Also:

- `Violin` gains an explicit signature (was `*args, **kw` — opaque to
  `help()`/IDEs).
- `by=`, `color_by=`, `size_by=` annotations widened to the full accessor
  union; new `channel_title()` derives legend titles honestly (column name or
  bare `col()` prints; derived/opaque accessors get no title instead of a
  repr dump). Guard tests in `test_accessors.py` pin the union per keyword.
- **Removed**: `Scatter(pyqtgraph_use_opengl=)` (deprecated, never wired) and
  `Scatter(matplotlib_rasterized=)` (backend leak; `handle.native()` is the
  escape hatch).

### Changed (wave 4 — [D123]/[D124]/[D125]/[D132] structural cleanup)

- **Honesty tables retired** ([D123]): every element now declares
  `HONORED_NATIVE` (one set, in core); a backend declares only its deltas —
  pyqtgraph's two (`Contour − filled`, `Image − interpolation`) are the whole
  per-backend surface. 78 byte-identical rows × 3 backends are gone.
- **Typed side-channels** ([D124]): the datashader/lazy-grid attributes
  (`_raster_source`/`_raster_agg`/`_raster_aggregate`/`_grid_source`) became
  one typed `_aux` slot (`RasterAux`/`GridAux`) with accessor helpers; the
  resolve pipeline dispatches on `DATA_KIND` instead of duck-typing; gridded
  reads go through `resolved_grid()`.
- **Entry-point backends** ([D125]): discovery is the `qtviz.backends`
  entry-point group — a third-party backend registers with zero qtviz edits;
  stale-metadata installs fall back to the built-ins.
- **Style uniformity** ([D132]): `alpha` on every visible element (added:
  Bars, Image, Mesh, Heatmap, ErrorBars, Contour); `line_width` uniform at
  1.5 (Quiver 1.0→1.5; ErrorBars gains the param — webengine error-bar
  thickness now follows it); Scatter takes the full 10-marker vocabulary;
  `axis="y2"` on every tabular xy element (added: Bars, Area, Spread, Stem,
  Histogram, Ecdf, ErrorBars).
- Benchmarks pass unchanged post-IR ([D126] settled: Curve/Bars stay native;
  [D127]: Pie stays absent on pyqtgraph).

### Changed (wave 3 — [D129]/[D130]/[D131] semantic surface + more lowering)

- **[D130] one colormap spec**: `norm=` accepts a name or `qv.Norm(kind, *,
  gamma=, linthresh=, levels=)` (new public name); `clim=(lo, hi)` is the
  separate range clamp. Replaces `vmin/vmax/gamma/linthresh/levels` on
  Image/Mesh/Heatmap and `Scatter(color_norm=)` (now `norm=`). A `Norm`
  parameter set for a kind that ignores it raises — the old "gamma needs
  power" mistakes are structurally impossible.
- **Spread redesigned** ([D129]): `Spread(data, x=|y=, lo=, hi=)` — exactly
  one of `x`/`y` picks the orientation; six mutually-constrained accessors
  become three. Lowers to a `Band` mark on every backend.
- **Streamlines is data-first** ([D129]): `Streamlines({"u": U, "v": V},
  extent=…, u=, v=)` — u/v are full channel accessors (expressions/callables
  work), structurally identical to Quiver; the 2-D grid contract is checked
  at geometry time.
- **`annotate=` union** ([D131]): `True` ≡ `"auto"`, `False` ≡ off, a format
  spec picks the text — one rule on Bars/Heatmap/Contour.
- **Ecdf lowers** to a post-step `Polyline`; `Band` joins the drawn mark set.
- **Tier amendments** (recorded in the design doc): the stats/raster family
  (Histogram, Bars, Area, BoxPlot, Violin, Heatmap, Contour) stays native —
  their numbers are already core-computed ([D67]/[D93]/[D105]); the per-backend
  remainder is engine bar/fill idioms and category-axis side effects a forced
  lowering would visibly change.

### Internal (wave 2 — the geometry tail renders through marks)

- Per-backend mark adapters (`backends/*/_marks.py`): ~7 drawers each, written
  once; `render_lowered` dispatches any element whose `lower()` is overridden.
  Native registrations win (fast-path override) — Scatter/Curve/Image/Mesh/
  Pie/Bars untouched.
- **12 elements now render through one core lowering** (Quiver, Streamlines,
  Stem + the 9 annotations): 12 renderer entries deleted from each native
  backend, the webengine annotation isinstance ladder deleted, their HONORED
  rows replaced by per-element `HONORED_BY_LOWERING` + the tier-1 perturbation
  guard. Migration gate: pre/post captures pixel-identical; the mpl/pg-heavy
  example screenshots are byte-identical.
- Event wiring declared, not isinstance'd ([D124]): brush registration via
  `Element.select_xy()` (Scatter/Curve/Stem), pick wiring via
  `Markers.pickable` inside the adapters.
- Tier amendments recorded in the design doc: **ErrorBars stays native**
  (every engine uses its native errorbar primitive with delta/cap semantics);
  **`ArrowMark` added** to the vocabulary (engine-native screen-space heads).
- Native escape-hatch types changed for shapes: one Polygon patch (mpl) / one
  svg-path shape (webengine) built from the shared core geometry — the
  `handle.native()` return type is non-contractual (docs/stability.md).

### Internal (wave 0 — IR foundation, no behavior change)

- `core/marks.py` — the typed Mark vocabulary ([D121]): 8 frozen mark types
  (`Polyline`, `Markers`, `Band`, `Rects`, `PolygonMark`, `TextMark`,
  `Rule`, `SpanMark`) with resolved `Stroke`/`Fill` style and
  `structurally_equal`, the [D123] honesty primitive. Positions are linear
  data space; log pretransform becomes a pyqtgraph-adapter concern.
- `core/lowering.py` — `LowerContext`/`Lowered`/`resolve_color`;
  `Element.lower()` hook ([D122], default "does not lower") with a pilot
  `Quiver.lower()` proving mark-level golden parity against
  `resolved_segments()`. Not yet on the render path (wave 2 flips backends
  to draw marks).
- [D124] groundwork: `Element.data` always resolves (`None` on data-less
  elements), `DATA_KIND` metadata, `select_xy()` hook,
  `HONORED_BY_LOWERING` declaration.
- [D125] backend protocol formalized: `honored_options()` and
  `requires_display` join the `Backend` protocol; `export(fmt, path, *,
  dpi=, transparent=)` widened on the base handle (composite export now
  warns instead of silently ignoring `dpi`/`transparent`).

## [Unreleased]

Parity program ([`design/parity-program.md`](design/parity-program.md)) — the
post-1.0 arc growing the vocabulary and axes toward "the everyday figures of
the popular libraries, declaratively" ([D83]).

### Added

- **Wave 1.5 — fields & flow** (roadmap-post-rerun [D117]/[D118]):
  `Contour(labels=)` — inline level labels placed once in core (marching
  squares → longest-line midpoint, upright tangent angle, background mask
  segment), identical across backends; and `Streamlines(u, v, bounds=,
  density=)` — the last member of the 2-D field quartet, integrated in
  core (RK4 both directions, bilinear interpolation, a 30×30·density
  spacing mask) and drawn as the same two-polyline primitive as Quiver.
- **Wave 1.4 — finish & honesty** (roadmap-post-rerun [D111]–[D115]):
  `Stem(data, x=, y=, baseline=, marker=)` — lollipop/stem series drawn as
  one pair-connected polyline + a pickable head layer ([D115]);
  `Quiver(key=, key_label=)` — a truthful legend-based reference key
  ([D112]); `Heatmap(cell_labels=)` with core-computed WCAG contrast and a
  ~400-cell guard ([D113]); `norm="symlog"` (`linthresh=`) and
  `norm="boundary"` (`levels=`) on Image/Heatmap/Mesh with honest
  colorbars ([D114]); Mesh edge validation that names the curvilinear
  boundary ([D111]); `ErrorBars(lo_limit=, hi_limit=)` arrow caps —
  "the true value lies beyond" — via the [D107] quiver construction
  ([D116]).
- **Fixed:** datashader autorange drift — a datashaded view no longer
  zooms out over time; the raster stops feeding autorange/dataLim after
  the first re-aggregation (P2 bug).
- **Meshes & vector fields (roadmap wave 3).** `Mesh(values, x_edges=,
  y_edges=)` — pcolormesh with non-uniform cell edges, sharing the [D105]
  norm pipeline (`colormap`/`norm`/`vmin`/`vmax`/`gamma`) — and
  `Quiver(data, x=, y=, u=, v=)` — arrow fields whose geometry (auto
  scale, ±25° barb heads) is computed once in core and drawn as two cheap
  polylines on every backend ([D106]/[D107]).
- **Mosaic layouts, ratios, and a real suptitle ([D108]).**
  `Layout.mosaic("AAB\nCCB", A=…, B=…, C=…)` builds grids with spanning
  panes from an ASCII plan (the `subplot_mosaic` precedent; `.` is a
  hole). `LayoutOptions` gains `width_ratios`/`height_ratios`, and the
  long-dead `LayoutOptions.title` now renders as the container suptitle.
  Grid shape is decided in one core helper (`grid_geometry`) shared by
  the matplotlib figure, the pyqtgraph layout, and the Qt host — which
  also makes `rows` honored everywhere. rows/title graduate out of the
  [D109] warning set on every grid consumer.

- **Axis & tick control (roadmap wave 2).** `AxisSpec` gains explicit
  `ticks`/`tick_labels` (data-space everywhere — pyqtgraph logifies them,
  date axes convert to ms; labels optional, the active format still
  applies without them), `minor=` ticks, and `tick_rotation` (matplotlib +
  Plotly; pyqtgraph has no stable rotation API and warns via [D109]).
  `tick_format` accepts one-field templates (`"${:,.0f}"`, `"{:.0f} ms"`),
  translated to Plotly prefix/format/suffix. Time axes get
  **calendar-aligned ticks on matplotlib** from one core ladder
  (seconds→minutes→hours→days→months→1/2/5-scaled years), with the
  formatter using the same strftime spec so positions and labels agree.
- **Raster color norms ([D105]).** `Image`/`Heatmap` gain
  `norm="linear"|"log"|"power"`, `vmin`/`vmax`, `gamma` — normalized once
  in core so backends color bit-identically. Colorbars appear only when
  the norm surface is engaged: matplotlib's ticks denormalize back to
  data values; pyqtgraph shows a gradient bar (linear) or the
  [D48]-honest endpoints key (non-linear); Plotly keeps its native
  colorbar for linear and hides the scale for non-linear.
- **Streaming × datashader composes ([D77] ladder, retrospective §4.2).**
  A `scale="datashader"` element over a `qv.stream` no longer rebuilds
  the world on every append: its `RasterController` — which reads the
  live source at each aggregation — exposes `refresh()`, and
  `set_element_data` routes datashaded elements to it. Appends now
  re-aggregate the current viewport off-thread (debounced, stale-dropped)
  with the native raster item kept in place, on pyqtgraph *and*
  matplotlib (its first streaming fast path).

- **Surface-option honor-or-warn ([D109]).** The anti-silent-drop contract
  now covers `OverlayOptions`/`AxisSpec`/`LayoutOptions` too: consumers
  declare what they honor (the three backends honor the full surface —
  the parity program wired it all; backend-hosted grids honor
  `cols`/`link_*`; the Qt layout host honors `cols`/`spacing`/tab/dock
  chrome) and anything set-but-unhonored warns once. `LayoutOptions.rows`
  and `.title` — the audit's recurring silent no-ops — now warn everywhere
  until [D108] wires them.

- **Per-point style channels ([D100], the wave's architectural item).**
  `Bars(color_by=)` colors each bar — categorical palette + key, or a
  continuous ramp + colorbar — on all three backends. `Curve(color_by=)`
  colors per *segment*: a categorical column splits into per-category
  sub-lines through one shared core split (identical on every backend,
  with a categorical key); a continuous column renders as a matplotlib
  `LineCollection` with the shared ramp + colorbar, and warns down to a
  single-color line on pyqtgraph/webengine (neither engine has a
  gradient-polyline primitive — value-level honesty). `color_by` elements
  emit their own key and opt out of the swatch legend ([D60] rule).

- **Annotation wave ([D96]/[D97], roadmap wave 1).** `Arrow(x0,y0,x1,y1,
  head=)` — the pointing half of `annotate`; `Text` gains `rotation`
  (CCW degrees on every backend), `anchor_v`, and `frame=` (a theme-styled
  box); shape annotations `Rect`/`Ellipse`/`Polygon` (outline-first,
  `fill=` opt-in, data-space under log via shared core geometry). All
  [D70]-class chrome: no palette slot, no events; Plotly draws them as
  layout shapes/annotations — whose coordinates now also follow date axes
  (epoch-ms) instead of landing in 1970.
- **Bar value labels ([D98]).** `Bars(bar_labels="auto"|<format-spec>)` —
  formatted through the tick vocabulary; outside for simple/grouped bars,
  centered inside stacked segments; all three backends.
- **Series polish pack ([D99]).** `Spread` gains the horizontal
  orientation (`y=`/`x_lo=`/`x_hi=` — `fill_betweenx` parity);
  `RefLine(slope, intercept)` — the `axline` analog (warns-and-drops
  under log; a long finite segment on webengine); `line_style` accepts
  on/off dash tuples in points everywhere it exists; `Curve(marker_every=)`
  thins markers; five new marker shapes (`triangle_down`, `plus`, `star`,
  `pentagon`, `hexagon`) — and the pre-existing wart where pyqtgraph's
  `triangle` pointed **down** (pg `"t"`) while mpl/Plotly pointed up is
  fixed (`"t1"`).

- **Calendar-time axes ([D94] — [D62] reversed by owner, 2026-07-31).** The
  canonical time data-space is **epoch seconds (UTC)** on every backend:
  datetime64 columns pass through the data layer and become seconds at the
  column seam; a linear axis auto-promotes to `scale="time"` when its data
  is datetime (warn-and-degrades to linear seconds on a backend without the
  capability). Calendar rendering is per-backend dressing — matplotlib gets
  an adaptive strftime formatter (granularity follows the visible span),
  pyqtgraph a UTC `DateAxisItem`, webengine a Plotly date axis (ms at its
  boundary, date-string relayouts parsed back to seconds). Events, brushes
  and `ViewState` stay plain floats in one space (R1), so time views
  round-trip across backend switches. `tick_format` accepts strftime
  patterns (`"%H:%M"`) on time axes. Previously datetime64 silently
  rendered as **nanosecond** floats — garbage axes with no warning.

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
- **Interaction ease ([D95]).** `View(..., toolbar=True)` shows the
  backend's native toolbar where one exists (matplotlib's pan/zoom
  navigation bar; pyqtgraph/webengine already interact natively → no-op),
  recreated across rebuilds and backend switches. matplotlib gains an
  interactive rubber-band brush: drag on any surface with brushable elements
  emits the same `SelectEvent`s as the programmatic `select_bounds`.
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

### Removed

- **`qtviz.Options`** — deprecated in 0.2, promised "importable through
  1.0", removed this cycle exactly as `docs/stability.md` scheduled. Set
  styling on elements (`Scatter(color=…, alpha=…)`).

### Deprecated

- `Scatter(pyqtgraph_use_opengl=...)` — never wired to anything; warns now
  (owner ruling, 2026-07-31). Removal follows the ≥2-minor warning policy
  (it cannot ride the same release its warning first ships in). pyqtgraph's
  default raster path covers large scatters; huge data goes through
  `scale="datashader"`.

### Fixed

- **Teardown lifecycle hygiene.** Views now release their final render
  handle on destruction (previously only replaced handles were disposed),
  matplotlib canvases can no longer run a queued idle-draw after deletion,
  and live-stream plumbing was moved off churned per-rebuild QObjects onto
  the View — eliminating a long-standing intermittent teardown segfault
  and a "Slot not found" flake under rapid rebuilds.

Defects surfaced by the matplotlib-gallery audit
([`design/matplotlib-gallery-audit.md`](design/matplotlib-gallery-audit.md) §2):

- **The interactive brush no longer corrupts matplotlib autoscale (P1).**
  The [D95] `RectangleSelector` parks a 0×0 rectangle at (0, 0) whose extent
  joined `Axes.dataLim` — and the selector's construction unstales the view
  limits, baking the polluted range in — so any autoscaled data far from the
  origin (every epoch-seconds time axis) rendered zoomed out to 1970. The
  data limits are now snapshotted around selector creation and autoscale is
  re-run.
- **`Histogram` gains `alpha=`** (honored on all three backends) — overlaid
  translucent histograms no longer need the 8-digit-hex color workaround.
- **matplotlib colormap names resolve case-insensitively** with the same
  warn-fallback-to-viridis contract as the other backends
  (`colormap="greys"` used to raise from inside matplotlib).

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
