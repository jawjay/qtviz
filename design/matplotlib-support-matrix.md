# matplotlib support in qtviz — the current-state matrix (1.0)

> **Purpose.** A precise, current-state answer to "what of the matplotlib API can
> I reach through qtviz, and what should I expect for everything else?" It walks
> matplotlib's API surface group by group and states, for each capability, whether
> qtviz's matplotlib backend supports it, partially supports it, degrades, or
> doesn't model it at all — and what the *expectation* is in each case (warning,
> silent no-op, escape hatch, or non-goal).
>
> Facts are read directly from `src/qtviz/backends/matplotlib/` and the element /
> options / event sources at **qtviz 1.0.0 + the parity program** (2026-07-31,
> [`parity-program.md`](parity-program.md) increments 1–6 + 8 — step/marker
> curves, wired horizontal bars, shared histogram binning, heatmap data
> coordinates, `Area`/`Ecdf`/`Pie`/`Contour`, tick formatting, twin axes, the
> grid toggle, `View(toolbar=True)` and the interactive brush), against
> **matplotlib ≥ 3.11** (the pinned floor in `pyproject.toml`). This supersedes the
> *coverage* half of [`matplotlib-capability-review.md`](matplotlib-capability-review.md),
> which was the pre-0.3 gap analysis that drove the improvement plan — most of its
> "[gap]" entries (axis scales, legends, annotations, box/violin, stacked bars,
> export knobs, composite export) have since landed and are documented here in
> their 1.0 form. Part 1 of that document (the matplotlib benchmark catalog)
> remains accurate and is not repeated.

---

## 0. How to read this — the five expectation tiers

qtviz is declarative: you never call matplotlib yourself. Support therefore means
"expressible in the `Element` / `Overlay` / `Layout` / `View` vocabulary and
rendered faithfully by the matplotlib backend." Every entry below sits in exactly
one tier:

| Tier | Meaning | What you observe |
|---|---|---|
| ✅ **Supported** | In the vocabulary, implemented, declared in `Capabilities` / the `HONORED` table, guarded by the conformance suite | It works; behavior matches the other backends |
| ◑ **Partial** | Works, with concrete caveats listed | It works within the stated bounds |
| ⚠️ **Warn-and-degrade** | The API accepts it; this backend doesn't honor it ([D51], spec §3.4) | One `QtvizWarning` per (backend, element, option), then a documented fallback |
| 🔇 **Silent no-op** | Accepted but ignored with **no** warning — these are warts, enumerated exhaustively in §11 | Nothing happens; nothing tells you |
| ❌ **Not modeled** | Not expressible in the qtviz vocabulary | Use the `handle.native()` escape hatch (§10) onto the live mpl `Axes`/`Figure`, or it's an explicit non-goal |

Two library-wide contracts frame everything:

- **Capability honesty ([D52]).** The backend's `Capabilities` block only declares
  what has a code path. The matplotlib backend declares: 2-D only, no OpenGL,
  `picking="native"`, `brush="approximate"`, range events, **no streaming**,
  **no animation**, `exports={png, svg, pdf}`, GUI-thread-only,
  `scales={linear, log, symlog}`, `max_recommended_points=100_000`.
- **Honor-or-warn ([D51]).** Any *recommended* option you set that the backend
  doesn't consume warns once and is ignored — never silently dropped. (The silent
  no-ops in §11 are things that sit *outside* the recommended-options contract;
  that's exactly why they're listed.)

**Role of this backend.** matplotlib is qtviz's "static + publication" engine:
CPU-rendered `FigureCanvasQTAgg`, vector export, slow-interactive. Fast
interaction is pyqtgraph's job; web interactivity is webengine's. `backend="auto"`
prefers pyqtgraph (registration priority) — you get matplotlib by asking for it
(`backend="matplotlib"` or a `backend_hint`).

---

## 1. Plot types — the element vocabulary vs `Axes.*`

### 1.1 What qtviz renders through matplotlib (18 of 19 elements)

| qtviz element | mpl call used | Honored options | Caveats |
|---|---|---|---|
| `Scatter` | `Axes.scatter` | `color`, `color_by`, `size`, `size_by`, `alpha`, `marker`, `color_norm`, `label` (+ `matplotlib_rasterized`) | ✅ 5 markers (`circle/square/triangle/diamond/cross` → `o/s/^/D/X`); `size_by` scales point diameters ~5–18 pt; `color_by` draws a categorical key or continuous colorbar (§4); `matplotlib_rasterized=True` rasterizes the collection inside vector exports |
| `Curve` | `Axes.plot` | `color`, `line_width`, `line_style`, `marker`, `step`, `alpha`, `label`, `axis` | ✅ 4 dash styles; `step=pre/mid/post` ([D84]), point markers, `axis="y2"` for the twin axis ([D88]) |
| `Bars` | `Axes.bar`/`barh` | `color`, `group`, `mode`, `orient`, `label` | ✅ grouped/stacked in either orientation with a categorical legend; categorical ticks follow the orientation |
| `Histogram` | shared core binning + `Axes.bar` | `bins`, `density`, `color`, `label` | ✅ binned once in core ([D93]) so all backends draw the same bars; numpy rule strings (`"fd"`, `"sturges"`, …) pass through, bad ones raise |
| `Image` | `Axes.imshow` | `colormap`, `interpolation` | ✅ `extent=bounds`, `origin="lower"`; any mpl colormap name; `nearest`/`bilinear`; 3-D arrays render as RGBA; also the render target for datashaded/regridded data (§8) |
| `Heatmap` | qtviz `grid_reduce` + `imshow` | `colormap`, `aggregator` | ✅ real reduction ([D69]); cells sit at their **data coordinates** (categorical axes get index positions + tick labels) ([D92]) |
| `ErrorBars` | `Axes.errorbar` (`fmt="o"`) | `direction`, `color`, `label` | ✅ symmetric or `(lo, hi)`; all three directions (`y`/`x`/`both`) draw the declared whiskers |
| `Spread` | `Axes.fill_between` | `color`, `alpha`, `label` | ✅ |
| `HLine` / `VLine` | `axhline` / `axvline` | `color`, `line_width`, `line_style`, `alpha`, `label` | ✅ default color is the theme foreground (chrome, not a palette slot) |
| `Span` | `axhspan` / `axvspan` | `color`, `alpha`, `label` | ✅ `orient="h"/"v"` |
| `Text` | `Axes.text` | `color`, `size`, `anchor` | ◑ `anchor` maps to horizontal alignment only; no vertical anchor, no rotation, no arrows/callouts |
| `BoxPlot` | `Axes.bxp` (stats precomputed) | `by`, `color`, `alpha`, `label` | ✅ qtviz computes the statistics (median, quartiles, 1.5·IQR whiskers, outliers) so all backends draw the *same numbers* ([D67]); `by=` → one box per category + legend |
| `Area` | `Axes.fill_between` | `group`, `mode`, `color`, `alpha`, `label` | ✅ zero-baseline fill; per-group overlay/stacked bands ([D84b]) |
| `Ecdf` | core `ecdf` + post-step `plot` | `color`, `line_width`, `alpha`, `label` | ✅ shared numbers ([D91]) |
| `Pie` | `Axes.pie` | `labels`, `hole`, `alpha` | ✅ donut via annular wedges; axes off; theme-palette slices ([D90]) |
| `Contour` | `contour`/`contourf` | `levels`, `filled`, `colormap`, `line_width`, `label` | ✅ shared core levels ([D89]); themed colorbar when filled |
| `Violin` | qtviz KDE + `fill_betweenx` | `by`, `color`, `alpha`, `label` | ✅ Gaussian KDE, Scott's rule — deliberately **not** `Axes.violinplot`, same [D67] rationale |
| `RawFigure` | — | — | ❌ **webengine-only** by design (it wraps Plotly/Bokeh/HoloViews figures). Notably there is **no passthrough for an existing matplotlib `Figure`** — you cannot hand qtviz a figure you built yourself |

Interactivity on annotations (dragging an `HLine` threshold, resizing a `Span`)
is deliberately not modeled — reach the live artist via `handle.native()` (§10).

### 1.2 matplotlib plot types with no qtviz analog ❌

You cannot express these declaratively; the expectation is the `handle.native()`
escape hatch (draw them onto the qtviz-managed `Axes` yourself, §10), or upstream
computation + an existing element:

- **Areas & shapes:** `fill` (arbitrary polygons), `broken_barh`, `stem`.
  (`step`/`stairs` → `Curve(step=…)`; `stackplot` → `Area(group=, mode="stacked")`.)
- **Statistical:** `hexbin`, `hist2d` (the datashader count-raster is the qtviz
  analog for both 2-D density types), `eventplot`, `acorr`/`xcorr`.
  (`ecdf` → `Ecdf`; `pie` → `Pie`.)
- **Contours:** `clabel` (inline level labels) — `contour`/`contourf` are `Contour` now.
- **Vector fields:** `quiver`, `streamplot`, `barbs`.
- **Unstructured meshes:** `tripcolor`, `triplot`, `tricontour(f)`.
- **Gridded variants:** `pcolor`/`pcolormesh` (irregular cell edges), `spy`.
- **Spectral:** `psd`, `specgram`, etc. — explicit non-goal; compute upstream,
  plot a `Curve`/`Image`.
- **Structural:** `table`, `bar_label`, `annotate` with arrows/connection styles,
  `axline` (arbitrary-slope reference line — only h/v exist), `hlines`/`vlines`
  (multi-segment collections).
- **3-D** (`mpl_toolkits.mplot3d`): explicit non-goal for native backends
  (`dimensions={2}`, [D52]); the supported 3-D path is `RawFigure` + Plotly on
  webengine.

---

## 2. Axes, scales, and ticks

| matplotlib capability | Status | Expectation |
|---|---|---|
| `set_xscale/yscale("log")` | ✅ | `AxisSpec(scale="log")` per axis; mpl transforms data itself and `get_xlim()` stays in data space, so events/state need no conversion ([D59]/R1) |
| `"symlog"` | ✅ | **matplotlib-only among qtviz backends** — the same Overlay on pyqtgraph/webengine warns-and-degrades to linear |
| `"time"` (datetime axes) | ⚠️ reserved | Accepted by `AxisSpec`, warns and renders **linear** on every backend; datetime axes are deprioritized post-1.0 |
| `logit`, `asinh`, `FuncScale`, custom scales | ❌ | Not in the scale vocabulary (`linear/log/symlog/time`); `AxisSpec` **raises** `ValidationError` on anything else |
| Scales on raster surfaces | ⚠️ | A surface holding any `Image`/`Heatmap` (incl. datashaded) **forces linear** with a warning — rasters are never log-transformed ([D59]) |
| `set_xlim/ylim` | ✅ | Declarative `AxisSpec(lim=(lo, hi))`, or imperative `handle.restore_state(ViewState(...))` |
| `invert_xaxis/yaxis` | ✅ | `AxisSpec(invert=True)` |
| `set_aspect` | ✅ | `OverlayOptions(aspect=…)` (float) |
| `set_title`, `set_xlabel/ylabel` | ✅ | `OverlayOptions(title=…, x_label=…, y_label=…)`; themed color + font size |
| Tick **formatters** | ✅ | `AxisSpec(tick_format=…)`: Python format-spec strings + `"eng"` (SI), wired on every backend ([D86]); custom *locators* remain escape-hatch territory |
| `twinx` (dual y) | ✅ | `axis="y2"` on `Curve`/`Scatter` + `OverlayOptions(y2=AxisSpec(...))` ([D88]); `ViewState.y2_range` round-trips. `twiny` (dual x) stays unmodeled |
| `secondary_xaxis/yaxis` | ❌ | Same as above |
| `sharex`/`sharey` | ✅ | `LayoutOptions(link_x=True, link_y=True)` on a grid `Layout` → real mpl `sharex`/`sharey` against the first axes |
| Projections (`polar`, geographic, custom) | ❌ | Rectilinear only; non-goal territory |

---

## 3. Color, colormaps, normalization

| matplotlib capability | Status | Expectation |
|---|---|---|
| Named colormaps on rasters | ✅ | `Image(colormap=…)` / `Heatmap(colormap=…)` pass the string straight to mpl — **any registered mpl colormap name works on this backend** (portability caveat: other backends resolve names from their own registries) |
| Categorical series colors | ✅ | Theme palette cycling by surface slot (`series_index_map`, [D70]) — identical assignment across backends; annotations are chrome and don't consume slots |
| `color_by` (continuous) | ✅ | viridis ramp + a real `Figure.colorbar` when `color_norm="linear"` |
| `color_by` (categorical) | ✅ | palette swatches + a patch-based legend key |
| `LogNorm`-style mapping | ◑ | `Scatter(color_norm="log")` norms the mapped column, but the key degrades to an **endpoints-only** legend (min/max patches) rather than a continuous colorbar — deliberately, so a non-linear ramp is never presented as linear ([D48]) |
| `BoundaryNorm`, `TwoSlopeNorm`, `CenteredNorm`, `PowerNorm`, … | ❌ | Only `linear`/`log` in the `color_norm` vocabulary; constructor **raises** on anything else |
| Custom palettes | ✅ | `Theme(palette=Palette.from_hex([...]))` |
| Hatching, fill patterns, custom dash sequences | ❌ | 4 named dash styles and 5 markers are the whole style vocabulary |
| `rcParams` / style sheets | ❌ (incidental) | Not modeled. Global `rcParams` you set yourself *will* leak into qtviz figures (same process) — unsupported, untested, at your own risk |

---

## 4. Legends and colorbars

First-class since 0.3 ([D60]):

- ✅ **Aggregated overlay legend** — every element with `label=` contributes a
  `LegendEntry`; entries merge *into* any color-mapping key already drawn (a
  `color_by` key is never clobbered by labels, and vice versa).
- ✅ **Placement** — `OverlayOptions(legend_position=…)`: `auto` (mpl's default
  placement), `right` (`upper right`), `top` (`upper center`).
- ✅ **Suppression** — `legend=False` or `legend_position="none"` silences *every*
  legend path on the surface, including datashaded-raster keys and colorbars.
- ✅ **Colorbar lifecycle** — on dynamic re-aggregation (datashader), the previous
  colorbar is removed and redrawn, never stacked.
- ◑ **Fixed styling** — legend font size (8 pt), frame alpha (0.85) and the
  colorbar geometry are not configurable; matplotlib's custom handlers, multiple
  legends per axes, and `Figure.legend` are not modeled.

---

## 5. Theming (vs `rcParams` / style sheets)

`Theme` is a deliberately small backend-agnostic surface, not an rcParams mirror:

| Theme field | Applied on mpl? | How |
|---|---|---|
| `background` | ✅ | figure patch + axes facecolor |
| `foreground` | ✅ | spines, ticks, axis labels, title, legend text |
| `grid` | ✅ | themed color, alpha 0.5; `OverlayOptions(grid=False)` turns it off ([D87]) |
| `palette` | ✅ | series color cycling + categorical swatches |
| `font_size` / `title_size` | ✅ | axis labels / title (set via `OverlayOptions`) — **not** tick labels |
| `font_family` | 🔇 | **not applied on this backend** (webengine applies it; mpl ignores it — §11) |

`OverlayOptions.background` (per-surface override) ✅ sets the **plot area** on
all three backends (mpl axes facecolor / pyqtgraph ViewBox / plotly
`plot_bgcolor`); the figure/widget chrome stays on the theme. `Theme.light()` /
`dark()` / `from_qt_palette()` all work.

---

## 6. Layout and figure composition

| matplotlib capability | Status | Expectation |
|---|---|---|
| `subplots` grid | ✅ | `Layout(kind="grid")` renders as **subplots in one mpl `Figure`** when all panes are matplotlib (`can_host("grid")`); `cols` honored, `link_x`/`link_y` → `sharex`/`sharey` |
| Grid shape control | ◑ | shape is derived from `cols` only — **`LayoutOptions.rows` is ignored** by the single-figure path (§11); `spacing` applies only to the Qt-hosted (mixed-backend) grid, not within a figure |
| `tight_layout` / `constrained_layout` | ❌ | No layout-engine knobs; mpl default spacing |
| `subplot_mosaic`, spanning cells, `subfigures` | ❌ | No cell spanning or ragged/nested mosaic |
| Splitter / tabs / dock panes | ✅ | `Layout.splitter/tabs/…` — **beyond matplotlib**: real Qt containers; each mpl pane becomes its own `Figure` inside a `CompositeRenderHandle` |
| Mixed-backend panes | ✅ | **beyond matplotlib** — an mpl pane next to pyqtgraph/webengine panes in one window, one merged event bus |
| Inset axes, `indicate_inset_zoom` | ❌ | Escape hatch only |

---

## 7. Interaction and events

This is the "static + slow-interactive" backend. The typed event vocabulary is
five events; here is exactly what matplotlib emits:

| Event | Status | How it's produced on mpl |
|---|---|---|
| `RangeEvent` | ✅ | `xlim_changed`/`ylim_changed` callbacks — fires on *any* limit change (toolbar zoom, `restore_state`, code) |
| `PickEvent` | ◑ | **`Scatter` only** (PathCollection picker). No pick on `Curve`, `Bars`, or anything else — pyqtgraph/webengine are broader here |
| `HoverEvent` | ◑ | **datashaded rasters only**, carrying the aggregated `value` under the cursor ([D46]). No hover on ordinary elements |
| `SelectEvent` | ◑ | `brush="approximate"`: **programmatic only** — `handle.select_bounds(ax_index, …)` computes row indices per selectable element. **No interactive rubber-band** is wired (no `RectangleSelector`); brushing a datashaded view emits bounds-only events (`indices=[]`, [D78]) |
| `TapEvent` | ❌ | Never emitted by this backend |

**Pan/zoom expectation:** `qv.View(..., toolbar=True)` attaches matplotlib's
navigation toolbar ([D95]) — limit changes flow into `RangeEvent`s and drive
datashader re-aggregation. Surfaces with brushable elements also get an
interactive rubber-band brush (drag → `SelectEvent`s, same masking as
`select_bounds`). mpl's raw event system
(`scroll_event`, `key_press_event`, `draw_event`, …) is not surfaced; connect via
the escape hatch if needed.

**State:** `capture_state()`/`restore_state()` round-trip x/y ranges in data
space — but only for the **first** axes of a multi-surface figure;
`ViewState.selection` is not captured. This is what makes backend switching
resume at the same viewport.

---

## 8. Big data: the datashader / lazy-grid path ✅

Fully supported on this backend, at parity with pyqtgraph:

- `Scatter(..., scale="datashader")` / `Curve(...)` resolve to an `Image`; the
  raster **re-aggregates to the viewport** on every limit change at the axes'
  on-screen pixel size, debounced through the shared `RasterController`.
- All datashader aggregators in the vocabulary (`count/sum/mean/max/min/std/any/by`)
  work — aggregation is a pipeline step, backend-independent.
- Hover reports the aggregated value under the cursor; the legend/colorbar
  refreshes with each re-aggregation; theme palette drives categorical shading.
- Decimated lazy grids (dask/xarray/zarr, [D74]) regrid to the viewport the same
  way ([D75]).
- Caveats: raster surfaces force **linear** scales (§2); brush through a raster is
  bounds-only ([D78]); the known **autorange-drift** bug (datashaded views zoom
  out over time) applies here as elsewhere.

`max_recommended_points` is 100 k — `backend="auto"` routes >1 M-point data to
the backend that declares the highest ceiling rather than raw mpl artists.

---

## 9. Output and export

| Capability | Status | Expectation |
|---|---|---|
| PNG / SVG / PDF | ✅ | `handle.export(fmt, path)` → `savefig`; declared in `Capabilities.exports` — the **only** backend with vector export (pyqtgraph/webengine are png-only) |
| `dpi=`, `transparent=` | ✅ | Both honored ([D72]) |
| `bbox_inches="tight"`, `metadata=`, `facecolor=`, PIL kwargs | ❌ | Not in the `export` signature |
| EPS / PS / PGF / WebP / TIFF | ❌ | Format vocabulary is png/svg/pdf |
| Mixed-backend layout export | ◑ | A `CompositeRenderHandle` exports **png only** (one `QWidget.grab()` of the container); per-pane vector export remains available via `handle.children[i].export(...)` — a single vector surface across backends is a stated non-goal ([D58]/R6) |
| Animation / movie writers (`FuncAnimation`) | ❌ | `animation=False` — honest capability; reactive `Signal[Node]` re-render covers data-driven updates, not frame timelines |

---

## 10. The escape hatch — what "not modeled" actually costs you

Anything in §1.2/§2/§3 marked ❌ is reachable, because the backend hands you live
matplotlib objects ([D53]):

- `view.native(element_id)` / `handle.native(id)` → the mpl **`Artist`** for an
  element (a `PathCollection`, `Line2D`, `AxesImage`, …).
- `handle.axes` → the list of live **`Axes`** (so `handle.axes[0].contourf(...)`,
  `.twinx()`, `.annotate(...)`, `mpl_connect(...)` all work).
- `artist.figure` → the **`Figure`** and canvas.

Expectations when you use it: (1) it's **non-portable** — code written against it
breaks the "swap the backend" promise; (2) the natives map is **rebuilt on every
re-render** (theme/backend/root change), so anything you drew by hand is lost on
rebuild; (3) you're on matplotlib's thread rules — GUI thread only
(`threading_model="gui_only"`, enforced by `@require_gui_thread`).

Since streaming is `streaming=False` here, a live `qv.stream` ref still works —
but every append triggers a **full View rebuild** (the honest slow path; the
docstring calls it out by name). Use pyqtgraph/webengine for streaming dashboards.

---

## 11. Known warts — the exhaustive silent-no-op / surprise list 🔇

Everything above degrades loudly or is documented; these are the cases that
currently do **not** warn. If you're debugging "I set X and nothing happened,"
look here first:

| # | Surface | Behavior | Why it escapes honor-or-warn |
|---|---|---|---|
| 1 | `LayoutOptions(rows=…)` on an all-mpl grid | Ignored — shape derives from `cols` alone | Layout options aren't capability-gated |
| 2 | `LayoutOptions(spacing=…)` on an all-mpl grid | Ignored inside a single figure (applies only to the Qt-hosted mixed grid) | Same as #1 |
| 3 | `Theme(font_family=…)` | Not applied by the mpl backend | Theme fields aren't per-backend gated |
| 4 | `Text` with `$…$` | Renders as mathtext on this backend (mpl interprets it) but as literal text elsewhere | Incidental engine behavior — don't rely on it |
| 5 | `Scatter(pyqtgraph_use_opengl=…)` | Stored, read by no renderer (the pyqtgraph sibling of the fixed `matplotlib_rasterized`) | Not in `RECOMMENDED_OPTIONS`; wiring it has headless/OpenGL risk — open decision |

Fixed post-1.0.0 and moved out of this list: `matplotlib_rasterized`,
`OverlayOptions.background`, `ErrorBars(direction="both")` (the wart-fix
commit), then the parity program wired `tick_format` ([D86]), string
histogram-bin rules ([D93]), heatmap data coordinates ([D92]), `Bars.mode`
into honor-or-warn, and the `grid=` toggle ([D87]). The remaining rows are
accepted design edges, except #5 — the last dead backend-prefixed flag —
which needs a wire-or-deprecate call.

---

## 12. One-paragraph summary

Through qtviz you get matplotlib as a **publication-quality, vector-exporting
renderer of the full 14-element declarative vocabulary** — including statistical
elements with library-computed stats, annotations, first-class legends/colorbars,
log/symlog axes, grid layouts with shared axes, themes, and the complete
datashader big-data path with viewport re-aggregation and hover values. What you
do **not** get is matplotlib's breadth (no contours, vector fields, pie/ecdf/step,
twin axes, tick formatters, datetime axes, color norms beyond linear/log,
annotate-arrows, rcParams control) or its interactivity plumbing (no toolbar by
default, pick on Scatter only, no interactive brush, no streaming fast path, no
animation). The boundary is policed by two contracts — capabilities are honest,
and unsupported *recommended* options warn rather than vanish — with the five
silent exceptions catalogued in §11, and everything outside the vocabulary
reachable (non-portably) through `handle.native()` / `handle.axes`.
