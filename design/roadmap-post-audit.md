# Post-audit roadmap — closing the gallery gaps (1.1 → 1.3)

> **Input.** The 507-example gallery audit
> ([`matplotlib-gallery-audit.md`](matplotlib-gallery-audit.md)) left qtviz at
> 47% of in-scope examples achievable (57% in the core chart categories), with
> the 181 gaps concentrated in ten themes. This document turns those themes
> into a staged development roadmap with the design and architecture work
> called out per item. Decisions are numbered **[D96]–[D110]**, house style:
> recommendations to confirm at review, alternatives recorded. The audit's
> defects #1–#3 are already fixed (commit `d788caf`).
>
> **Frame.** Two tracks run in parallel post-1.0: this **vocabulary track**
> (gallery-gap driven) and the retrospective's **capability track**
> (streaming × datashader composition, hover for regridded arrays —
> [`retrospective-1.0.md`](retrospective-1.0.md) §4). This document schedules
> the first and reserves an interleave slot for the second so the
> differentiators don't starve while we chase parity.

## 0. Architectural read of the audit (what the gaps have in common)

Before the item list, the four structural observations that shape it:

1. **Almost everything is additive vocabulary, not architecture.** The [D70]
   annotation class, the `RENDERERS`/`HONORED` registries, and the
   conformance suite mean a new element or option lands as: one element file,
   three renderer functions, three `HONORED` entries, freeze-list/api.md
   rows — with honor-or-warn letting a backend ship partial support honestly.
   The seams the retrospective called load-bearing keep paying; no gap below
   requires touching the core contracts, with one exception (#3).
2. **"Compute in core, draw everywhere" ([D67]) is the recurring answer.**
   Color norms, quiver geometry, calendar-aligned time ticks, contour levels,
   box stats, histogram bins — whenever mpl solves something inside its
   engine, our portable answer is one numpy implementation feeding all three
   backends. This roadmap codifies that as the default pattern for every new
   capability ([D110]).
3. **The one true architectural extension is per-point style channels
   ([D100]).** A cluster of gaps (per-bar colors, multicolored lines,
   per-point markers, value-colored anything) share a root: the encoding
   pipeline (`channels()` → `map_colors`) currently serves only
   `Scatter.color_by/size_by`. Generalizing it to `Bars` and `Curve` is
   pipeline work, not renderer work — and it is the highest-leverage single
   change on the list.
4. **Surface options need the honesty machinery too.** Honor-or-warn covers
   *element* options; the audit and support matrix keep finding *surface*
   silent no-ops (`LayoutOptions.rows/spacing/title`, `tick_format` pre-D86).
   [D109] extends the conformance contract to `OverlayOptions`/`AxisSpec`/
   `LayoutOptions` so a surface option is honored, warned about, or doesn't
   exist.

## 1. Release map

| Release | Theme | Items | Gallery yield (≈) |
|---|---|---|---|
| **1.1 — Annotation & dressing** ✅ (shipped 2026-07-31) | the supporting cast of every real figure | [D96] Arrow + richer Text · [D97] Rect/Ellipse/Polygon · [D98] data labels · [D99] series polish pack · [D100] per-point channels · [D109] surface-option honesty · promised removals (`Options`, `pyqtgraph_use_opengl`) | ~45 examples ❌/◑ → ✅/◑ |
| **1.2 — Axis & tick control** (+ capability-track interleave) | ticks users actually ask for; time axes finished | [D101] explicit ticks/labels · [D102] format templates · [D103] minor ticks + rotation · [D104] calendar-aligned mpl time ticks · [D105] raster color norms · *interleave: streaming×datashader* | ~20 examples |
| **1.3 — Meshes, fields & layout composition** | scientific 2-D + real dashboards | [D106] `Mesh` (pcolormesh) · [D107] `Quiver` · [D108] mosaic layouts + ratios + suptitle | ~20 examples |
| **Parked register** | demand-gated subsystems | §5 | — |

Cadence unchanged: spec → discussion items → TDD increments → green commits;
direction confirmed at each release boundary.

## 2. Wave 1 (1.1) — annotation & dressing

### [D96] `Arrow` element + `Text` growing up
- **API.** `Arrow(x0, y0, x1, y1, *, head="end"|"both"|"none", color=None,
  line_width=1.5, alpha=1.0, label=None)` — a [D70] annotation (pure data,
  theme-foreground default, composes via `*`). `Text` gains
  `rotation: float = 0.0`, `anchor_v: "center"|"top"|"bottom"`, and
  `frame: bool = False` (a theme-bordered box).
- **Backends.** mpl: `annotate(""…, arrowprops)`/`FancyArrowPatch`; `Text` maps
  `rotation=`, `va=`, `bbox=`. pg: shaft as `PlotCurveItem` + head as
  `pg.ArrowItem` (angle from `atan2` in the *plotted* space — under log the
  endpoints logify first, the [D70] `_ref_scalar` rule); `TextItem` has
  native `angle` and anchor tuples. webengine: Plotly `layout.annotations`
  carry `ax/ay` in data refs and `textangle`/`yanchor` natively.
- **R1.** All coordinates data-space; rotation is visual-only — no event or
  state implications.
- **Alternative rejected:** a compound `Callout(text, at=…)` — two orthogonal
  primitives compose; revisit only if callout ergonomics demand sugar.
- Unlocks: `annotation_basic/demo`, `arrow_demo`, `fancyarrow` (basic forms),
  `text_rotation_*`, `bar-annotation` idioms across categories. Fixes audit
  defect #5. **Effort: M.**

### [D97] Shape annotations — `Rect`, `Ellipse`, `Polygon`
- **API.** `Rect(x0, y0, x1, y1, *, fill=True, …)` ·
  `Ellipse(cx, cy, rx, ry, *, angle=0.0, …)` · `Polygon(points, *, …)` —
  annotation-class (literal coordinates, no `DataRef`), standard
  color/line_width/alpha/label.
- **Backends.** mpl patches; pg `QGraphicsRect/Ellipse/PathItem` (the Violin
  renderer already proves the `QGraphicsPathItem` path); Plotly
  `layout.shapes` (`rect`/`circle`/`path`).
- **Design rule — shapes are data-space.** Under log scales positions
  transform like every annotation (pg logifies; mpl/plotly transform
  natively); an `Ellipse` therefore stops looking elliptical under log on
  *every* backend — consistent, documented, no gate needed.
- Unlocks: `confidence_ellipse` (with covariance math in the caller),
  `errorbars_and_boxes`, `broken_barh` (Rects), `fill` (Polygon), highlight
  boxes everywhere. **Effort: M.**

### [D98] Data labels
- **API.** `Bars(bar_labels=None|"auto"|<format-spec>)` — value labels using
  the [D86] tick-format vocabulary (`"auto"` → `%g`); later
  `Scatter(labels_by=<column>)` for point labels if demand shows.
- **Backends.** mpl `ax.bar_label`; pg one `TextItem` per bar (bars are
  small-n by nature); Plotly `text=`/`textposition` on bar traces.
- **Placement vocabulary** deliberately minimal: outside-end only (mpl
  default); inside/center variants wait for demand.
- Unlocks `bar_label_demo`, `hat_graph`, `horizontal_barchart_distribution`
  labels. **Effort: S.**

### [D99] Series polish pack (small, independently landable)
| Item | API | Backend notes | Effort |
|---|---|---|---|
| Horizontal band | `Spread(orient="v"\|"h")` (mirrors `Span`) | mpl `fill_betweenx`; pg `FillBetweenItem` is orientation-agnostic polygon fill; Plotly `fill="tonextx"` | S |
| Sloped reference line | `RefLine(slope, intercept, …)` ([D70] class) | mpl `axline` native; pg `InfiniteLine(angle=…)` — **verify pg's angle is data-space under unequal aspect during the spike**; webengine draws a spanning segment recomputed on range events (honest caveat, documented) | S–M |
| Custom dash | `line_style=(on, off, …)` tuple accepted everywhere `line_style` is | mpl `dashes=`; pg `pen.setDashPattern`; Plotly `dash="4px,2px"` | S |
| Marker thinning | `marker_every: int = 1` on Curve | mpl `markevery` native; pg/webengine draw the marker layer from sliced points (the mid-step dots pattern already does this on pg) | S |
| Marker breadth | +5 shapes: `star`, `plus`, `pentagon`, `hexagon`, `triangle_down` | all three engines have them natively | S |

### [D100] Per-point style channels — the architectural item
- **What.** Generalize the `color_by` encoding pipeline beyond Scatter:
  - `Bars(color_by=<column>)` — per-bar categorical palette (+ key) or
    continuous ramp (+ colorbar). All three backends take per-item color
    arrays natively. Straightforward.
  - `Curve(color_by=<column>)` — per-*segment* color. **Tiered by backend
    honesty:** categorical → split the curve into NaN-separated per-category
    sub-curves in core (cheap, fully portable); continuous → mpl
    `LineCollection` and Plotly per-segment traces natively, **pyqtgraph
    warns-and-degrades** initially (no native gradient polyline; per-segment
    items collapse at scale). The capability system exists precisely for
    this shape of partial support.
- **Architecture.** This extends `channels()` resolution + `map_colors` reuse,
  not renderers-only: the resolve pipeline already materializes a `color`
  role (Scatter precedent), so the change is per-element `channels()` +
  renderer consumption + one core helper for the categorical curve split.
  No new seams.
- Unlocks `multicolored_line`, `color_by_yvalue`, per-bar-color idioms, and
  is the single most-requested real-world styling feature (state-colored
  telemetry traces). **Effort: M–L (the pg continuous tier is the L).**

### [D109] Surface-option honesty
- Extend the honor-or-warn contract to `OverlayOptions`/`AxisSpec`/
  `LayoutOptions`: each backend declares `honored_surface_options()`, a
  `check_recommended`-equivalent warns on set-but-unhonored fields, and the
  conformance suite grows the matching matrix test. Immediately converts the
  known silent no-ops (`LayoutOptions.rows`/`spacing` on single-figure
  grids, `Theme.font_family` on mpl) into warnings, and wires or removes
  the dead `LayoutOptions.title` (see [D108] — wiring it as suptitle is the
  better half). **Effort: S–M, mostly test machinery.**

## 3. Wave 2 (1.2) — axis & tick control

### [D101] Explicit ticks and labels
`AxisSpec(ticks=[…], tick_labels=[…])` (labels optional; must zip). mpl
`set_ticks(labels=)`; pg `setTicks`; Plotly `tickvals/ticktext`. Covers
value→label mapping (`tick_labels_from_values`), business-day index axes
(`date_index_formatter` — plot against an integer index, label with dates),
and categorical relabeling. **Effort: S. The highest value-per-line item in
the wave.**

### [D102] Format templates
`tick_format` accepts a one-field `str.format` template: `"${:,.0f}"`,
`"{:.0f} ms"`. Core: trivial (probe-validated like [D86]). webengine:
translate `prefix + spec + suffix` templates to `tickprefix`/`tickformat`/
`ticksuffix`; anything else warns-and-degrades there (Plotly cannot run
Python templates). Covers `dollar_ticks` and friends. **Effort: S.**

### [D103] Minor ticks + tick label rotation
`AxisSpec(minor=False, tick_rotation=0.0)`. mpl `minorticks_on()` +
`tick_params(rotation=)`; Plotly `minor=` + `tickangle`; pg already draws
minor tick levels (no-op honor) but has no stable label-rotation API →
`tick_rotation` **warns on pg** until someone needs it enough to subclass
`AxisItem`. **Effort: S–M.**

### [D104] Calendar-aligned matplotlib time ticks
Finish [D94]: a core `time_ticks(lo, hi) -> (positions, spec)` that snaps to
year/month/week/day/hour boundaries, driving an mpl `Locator` subclass (pg's
`DateAxisItem` already does this natively; webengine native). One
implementation, mpl consumes it — and if pg's choices ever diverge
noticeably, pg can consume the same core function through a custom axis.
**Effort: M.**

### [D105] Raster color norms + explicit limits
- **API.** `norm="linear"|"log"|"symlog"|"power"`, `vmin=`, `vmax=`
  (+ `gamma` for power) on `Image`/`Heatmap`/`Contour`; `Scatter.color_norm`
  re-routed through the same path.
- **Architecture ([D110] pattern).** Normalize **in core**: one numpy
  transform producing the display grid + a tick map for the colorbar.
  Backends keep drawing linear data; colorbars get remapped tick labels via
  the existing legend machinery, and non-linear ramps keep the [D48] honesty
  treatment. This guarantees identical rendering across engines — the
  audit's `multi_image` (shared norm) falls out of explicit `vmin/vmax`.
- Unlocks `colormap_normalizations*`, `power_norm`, `contourf_log`,
  `multi_image`. **Effort: M.**

## 4. Wave 3 (1.3) — meshes, fields & layout composition

### [D106] `Mesh` — non-uniform rectilinear grids (pcolormesh)
- **API.** `Mesh(values2d, x_edges=<n+1>, y_edges=<m+1>, colormap=, norm=…)`;
  edges canonical (centers are `Heatmap`'s job).
- **Backends.** mpl `pcolormesh`; pg `PColorMeshItem` (exists upstream —
  **spike its maturity + perf first**, the one load-bearing risk of the
  wave); Plotly `heatmap` accepts non-uniform `x/y` arrays.
- Unlocks the `pcolor*`/`image_nonuniform`/`irregulardatagrid` family and a
  real scientific need (log-spaced frequency axes on spectrograms).
  **Effort: M (post-spike).**

### [D107] `Quiver` — vector fields
- **API.** `Quiver(data, x=, y=, u=, v=, scale="auto"|float, head_scale=1.0,
  color=, color_by=?)`.
- **Architecture.** Core computes shaft + arrowhead **segment geometry once**
  (NaN-separated polyline, [D110]); every backend draws two cheap primitives
  (segments + heads) — pixel-identical fields on all three engines, and pg
  gets it without a thousand `ArrowItem`s. mpl's native `quiver` is
  deliberately *not* used: one geometry, one meaning.
- Streamplot stays parked (needs an ODE integrator; different beast).
  **Effort: M.**

### [D108] Mosaic layouts, ratios, and a real suptitle
- **API.** `Layout.mosaic("AAB\nCCB", A=node, B=node, C=node)` (the
  `subplot_mosaic` precedent — ergonomic and unambiguous), plus
  `LayoutOptions(width_ratios=[…], height_ratios=[…])`, plus wiring the
  long-dead `LayoutOptions.title` as the container/figure title.
- **Architecture.** A pure parser in `core/compose` produces per-child
  `(row, col, rowspan, colspan)`; every host already supports spans natively
  (mpl `GridSpec`, pg `GraphicsLayout.addPlot(rowspan=)`, Qt
  `QGridLayout.addWidget(spans)`) — the uniform-grid assumption is the only
  thing being removed. Ratios: `GridSpec` ratios / Qt stretch factors / pg
  `QGraphicsGridLayout` stretch. Suptitle: mpl `fig.suptitle`; hosts add a
  label row.
- Unlocks the `gridspec_*`/`subplot2grid` family and — more importantly —
  real dashboard shapes (tall sidebar + main pane) without splitter nesting.
  **Effort: M.**

## 5. Parked register (demand-gated, with escape paths)

| Gap | Why parked | Cost if opened | Today's path |
|---|---|---|---|
| Polar / radar | a whole projection subsystem: angular R1 for events/state, pg has no polar surface (would be hand-built grid + transform), AxisSpec is rectilinear | L–XL | `RawFigure` + Plotly polar |
| Triangulated data (`tri*`) | needs a triangulation dependency (SciPy `Delaunay` or vendored contouring) + a `TriMesh` data contract | L | precompute onto a grid; `RawFigure` |
| Streamplot | field-line integrator (ODE) in core | M–L (after [D107]) | `RawFigure` |
| Inset / zoom-connector axes | composition-model change: surface-positioned child surfaces + event routing into insets | M–L | second pane + `link` + Span markers |
| Broken axes | two linked sub-axes masquerading as one; interacts with events/state | M | two panes, `link_y` |
| 3+ y axes | generalize `y2` → `yN` (pg pattern scales; mpl offset spines; Plotly positioned axes) | M | second pane |
| Hexbin | datashader covers the job with a different (better-scaling) geometry | — | `scale="datashader"` |
| Sankey, skew-T, bullseye, Hinton, packed bubbles | specialty diagrams, each its own geometry engine | M each | `RawFigure` |
| Locator/formatter callbacks | anti-declarative (unserializable callables at the surface seam) | — | [D101]/[D102] cover the sane cases |
| Figure-space text/images, path effects, agg filters | figure-chrome drawing, not data description | — | `handle.native()` |

## 6. Decisions summary (to confirm)

- **[D96]** `Arrow` element + `Text` rotation/v-anchor/frame — M
- **[D97]** `Rect`/`Ellipse`/`Polygon` annotations, data-space rule — M
- **[D98]** `Bars(bar_labels=)` via the tick-format vocabulary — S
- **[D99]** polish pack: `Spread.orient`, `RefLine`, dash tuples,
  `marker_every`, +5 markers — S each
- **[D100]** per-point channels: `Bars.color_by`, `Curve.color_by`
  (categorical portable / continuous tiered) — M–L, *architectural*
- **[D101]** `AxisSpec(ticks=, tick_labels=)` — S
- **[D102]** one-field format templates — S
- **[D103]** `minor=`, `tick_rotation=` (pg warns on rotation) — S–M
- **[D104]** calendar-aligned mpl time locator from core — M
- **[D105]** raster norms + vmin/vmax, normalized in core — M
- **[D106]** `Mesh` (edges-canonical pcolormesh); spike `PColorMeshItem` — M
- **[D107]** `Quiver` with core-computed shared geometry — M
- **[D108]** mosaic layouts + ratios + suptitle (wires dead `title`) — M
- **[D109]** surface-option honor-or-warn conformance — S–M
- **[D110]** codify "compute in core, draw everywhere" as the standing
  pattern for new vocabulary (norms, geometry, ticks) — process, not code

## 7. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Vocabulary sprawl erodes "hold it in your head" | the [D54] curation bar per element (common in ≥2 major libraries, portable to ≥2 backends, honest elsewhere); annotations stay data-less [D70]-class |
| 2 | Gallery-count bias optimizes for mpl's showcase, not users | waves are ordered by real-usage frequency (annotation/dressing first — every figure needs it) not by raw example count; parked register resists the tail |
| 3 | pg's weaker primitives (gradient lines, mesh, rotation) drag schedules | tiered honesty: ship mpl+webengine full, pg warn-and-degrade where the primitive is missing — the contract exists for exactly this |
| 4 | [D100] pipeline generalization destabilizes the resolve seam | it reuses the existing `color` role machinery (Scatter precedent); spike the `Curve` categorical split first — it's pure numpy |
| 5 | Parity work starves the differentiator track | the 1.2 interleave slot is reserved for streaming×datashader before wave 3 begins |
