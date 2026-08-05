# matplotlib — capability review & qtviz gap analysis

> **Purpose.** matplotlib is the most complete 2-D plotting surface in the Python
> ecosystem and the de-facto benchmark every other library is measured against.
> This document does two things: **(Part 1)** catalogues matplotlib's API,
> capabilities, and strengths as a benchmark, and **(Part 2)** maps qtviz's
> current surface against it to surface concrete weaknesses and gaps.
>
> This is an analysis document only — **no code changes** are implied by it. It
> was a companion to two internal registers (a capabilities-gap list and an
> outside-evaluator landscape assessment, both since retired); where those
> looked outward at the competitive field, this one drills into a single
> incumbent to find where qtviz falls short of "table stakes."
>
> **Caveats.** matplotlib facts are current to **v3.11.0 (June 2026)**, drawn from
> the official docs (Axes API reference, Plot-types gallery, release notes) and the
> live source tree. qtviz facts are read directly from `src/qtviz/` at the time of
> writing. Where qtviz's status is nuanced, the entry says so rather than
> collapsing to a tick or a cross.

---

# Part 1 — matplotlib as the benchmark

## 1.1 What matplotlib is

matplotlib is an **imperative, object-oriented 2-D plotting library** built on a
stable artist model: a `Figure` contains `Axes`, and every visible thing is an
`Artist` (`Line2D`, `Patch`, `Text`, `Collection`, `Image`, …). Two interfaces sit
on top — the stateful `pyplot` module (MATLAB-style) and the explicit
object-oriented API (`fig, ax = plt.subplots()`). It is CPU-rendered (Agg is the
core rasteriser), single-process, and renders the same scene to screen or to file
through interchangeable **backends**.

- **Latest release:** 3.11.0 (June 2026). Min Python 3.11.
- **Reach:** the foundation under seaborn, pandas `.plot`, plotnine, mplfinance,
  networkx drawing, scikit-image, astropy, xarray `.plot`, scikit-learn display
  utilities, and more. Its API is, in effect, an ecosystem standard.
- **Headline recent additions (3.7 → 3.11):** `Axes.ecdf`, `stairs`/`StepPatch`,
  `bar_label`, `axline`, `Axes.inset_axes`/`indicate_inset_zoom`,
  `Figure.subfigures`, `subplot_mosaic`, `secondary_xaxis`/`secondary_yaxis`,
  `AsinhScale`, `TwoSlopeNorm`/`CenteredNorm`/`FuncNorm`, PEP 561 type stubs, and
  in 3.11 a HarfBuzz/libraqm text overhaul (OpenType, bidi, i18n), `grouped_bar`,
  `pie_label`, and `MultiNorm`.

## 1.2 The plot-type catalog

This is matplotlib's single biggest strength: **breadth**. Every method below is
on `matplotlib.axes.Axes` (and mirrored on `pyplot`).

**Lines, markers, areas (basic):**
`plot`, `scatter`, `step`, `stairs`, `bar`, `barh`, `bar_label`, `grouped_bar`,
`broken_barh`, `stem`, `fill`, `fill_between`, `fill_betweenx`, `stackplot`,
`loglog`, `semilogx`, `semilogy`.

**Reference lines & spans:**
`axhline`, `axvline`, `axline` (arbitrary slope), `axhspan`, `axvspan`, `hlines`,
`vlines`, `arrow`.

**Statistical / distributions:**
`hist`, `hist2d`, `boxplot`, `bxp`, `violinplot`, `hexbin`, `ecdf`, `errorbar`,
`eventplot`, `pie`, `pie_label`, `acorr`, `xcorr`.

**Gridded arrays & images:**
`imshow`, `pcolor`, `pcolormesh`, `pcolorfast`, `matshow`, `spy`.

**Contours:** `contour`, `contourf`, `clabel`.

**Unstructured / triangulated** (`matplotlib.tri`):
`tripcolor`, `triplot`, `tricontour`, `tricontourf`, with `Triangulation` for
Delaunay meshes.

**Vector fields:** `quiver`, `quiverkey`, `streamplot`, `barbs`.

**Spectral / signal:** `psd`, `csd`, `cohere`, `specgram`, `magnitude_spectrum`,
`phase_spectrum`, `angle_spectrum`.

**Text & structural:** `text`, `annotate`, `table`, `legend`, plus inset/secondary
helpers (`inset_axes`, `indicate_inset`, `secondary_xaxis`, `secondary_yaxis`).

## 1.3 3-D (`mpl_toolkits.mplot3d`)

`scatter`, `plot`, `plot_surface`, `plot_wireframe`, `plot_trisurf`,
`contour`/`contourf`, `tricontour`/`tricontourf`, `bar`/`bar3d`, `quiver`,
`voxels`, `errorbar`, `stem`, `fill_between`, `text`, plus camera control
(`view_init`, `set_proj_type` ortho/persp, roll/focal-length). **Limitation:**
painter's-algorithm compositing (no depth buffer/lighting) → intersecting surfaces
render incorrectly; "presentation-grade," not a real 3-D engine.

## 1.4 Projections & scales

- **Projections:** `rectilinear` (default), `polar`, `3d`, and geographic
  `aitoff`/`hammer`/`lambert`/`mollweide`. **Custom projections** register via
  `matplotlib.projections.register_projection`. Real GIS maps come from the
  **cartopy** ecosystem (basemap is deprecated).
- **Axis scales:** `linear`, `log`, `symlog`, `logit`, `asinh`, `function`
  (`FuncScale`), `functionlog`; custom scales via `register_scale`. Underpinned by
  a full transform system (`matplotlib.transforms`: `Transform`, `Affine2D`,
  blended/composite transforms).
- **Tick machinery:** pluggable **locators** (`MaxNLocator`, `LogLocator`,
  `MultipleLocator`, date locators) and **formatters** (`ScalarFormatter`,
  `FuncFormatter`, `PercentFormatter`, `EngFormatter`, date formatters). Native
  **datetime axes** via `matplotlib.dates`. Categorical axes via `units`.

## 1.5 Styling, color, text, annotation

- **Colormaps:** registry (`matplotlib.colormaps`); perceptually-uniform (viridis,
  plasma, inferno, magma, cividis), sequential, diverging, cyclic, qualitative;
  `_r` reversed variants; `ListedColormap`/`LinearSegmentedColormap`.
- **Normalization:** `Normalize`, `LogNorm`, `SymLogNorm`, `AsinhNorm`,
  `PowerNorm`, `BoundaryNorm`, `TwoSlopeNorm`, `CenteredNorm`, `FuncNorm`,
  `NoNorm`, `MultiNorm` — i.e. fine control of value→color mapping.
- **Styling model:** every artist is individually styleable; `rcParams` global
  config; **style sheets** (`plt.style.use`, `.mplstyle`, bundled `ggplot`,
  `seaborn-v0_8-*`, `dark_background`, …).
- **Text:** built-in **mathtext** (TeX subset, no external dep), full **LaTeX**
  via `text.usetex`, and a **PGF/LaTeX** backend; HarfBuzz shaping + bidi + i18n in
  3.11. Hatching, fill patterns, marker styles, dash patterns.
- **Annotation:** `annotate` with rich `arrowprops`/connection styles and multiple
  coordinate systems, `FancyArrowPatch`, text bboxes.
- **Legends & colorbars:** first-class, highly configurable `legend` (custom
  handlers, `HandlerTuple`, manual handles, placement, multiple legends per axes)
  and `colorbar` (`Figure.colorbar`, any `ScalarMappable`, ticks/extend/label).
  `table` for tabular overlays.

## 1.6 Layout & figure composition

`subplots`, `GridSpec`/`GridSpecFromSubplotSpec`, `subplot_mosaic` (ASCII/nested
layouts with spanning), `add_gridspec`, `Figure.subfigures` (independent nested
figures). Layout engines: `constrained_layout` (recommended) and `tight_layout`.
Shared/twin axes: `sharex`/`sharey`, `twinx`/`twiny`, `secondary_xaxis`/`yaxis`
(with forward/inverse transforms). Inset axes (`inset_axes`,
`indicate_inset_zoom`) and `mpl_toolkits.axes_grid1` (`ImageGrid`, dividers).

## 1.7 Output & backends

- **Vector:** PDF, SVG/SVGZ, PS, EPS, **PGF** (LaTeX). **Raster:** PNG, JPG, TIFF,
  WebP (via Pillow), RGBA buffer. `savefig(dpi=, bbox_inches='tight', transparent=,
  facecolor=, metadata=, pil_kwargs=, …)`.
- **Backends:** core rasterisers Agg & Cairo; GUI: **QtAgg** (`FigureCanvasQTAgg`,
  PyQt6/PyQt5/PySide6/PySide2), TkAgg, GTK3/4, WxAgg, MacOSX; web/notebook:
  WebAgg, nbAgg, ipympl; file-only: PDF/PS/SVG/PGF.

## 1.8 Interaction & animation

- **Event system** (`canvas.mpl_connect`): `button_press/release_event`,
  `motion_notify_event`, `scroll_event`, `key_press/release_event`, `pick_event`,
  `draw_event`, `resize_event`, axes/figure enter/leave. Built-in pan/zoom toolbar.
- **Widgets** (`matplotlib.widgets`): `Slider`, `RangeSlider`, `Button`,
  `CheckButtons`, `RadioButtons`, `TextBox`, `Cursor`, `MultiCursor`,
  `SpanSelector`, `RectangleSelector`, `EllipseSelector`, `LassoSelector`,
  `PolygonSelector`.
- **Animation** (`matplotlib.animation`): `FuncAnimation`, `ArtistAnimation`;
  writers Pillow/FFMpeg/ImageMagick/HTML; **blitting** for fast partial redraws.

## 1.9 Ecosystem leverage

seaborn (statistical defaults + faceting), pandas `.plot`, plotnine
(grammar-of-graphics), mplfinance (candlesticks), networkx (`draw_networkx`),
astropy (`WCSAxes`), xarray `.plot`, scikit-learn display objects, squarify
(treemaps). Anything matplotlib-based composes onto a qtviz matplotlib axes if
that surface is exposed.

## 1.10 matplotlib's recognized weaknesses

The flip side — and exactly where a native-Qt library can win:

- **Interactivity is static-first** — no built-in hover tooltips, no data-space
  brushing model, web interactivity is bolt-on (nbagg/ipympl, boilerplate-heavy).
- **Large data / performance** — CPU/Agg only, no GPU/WebGL; high-density scatter
  and real-time streaming struggle (this is qtviz's pyqtgraph + Datashader wedge).
- **Live updates** are manual; blitting is fiddly; no streaming model.
- **3-D** is presentation-grade, not a real engine.
- **API verbosity / imperative-ness** — dual pyplot/OO interfaces; complex figures
  need substantial boilerplate; no declarative or value-hashed description (this is
  qtviz's *declarative* wedge).
- **Defaults** improved but still often "dressed up" with seaborn.

---

# Part 2 — qtviz coverage vs matplotlib

qtviz is **not trying to be matplotlib** — it is a declarative, multi-backend,
native-Qt, offline, big-data library whose matplotlib backend exists mainly for
*publication-quality export of the same `Element`*. So "matplotlib can do X and
qtviz can't" is sometimes a deliberate non-goal, not a defect. The matrix below
separates the two: each gap is tagged **[gap]** (a genuine weakness worth closing),
**[partial]**, or **[non-goal]** (out of scope by design, host Qt/`RawFigure`
covers it).

## 2.1 Capability matrix

Legend: ✅ supported · ◑ partial · ❌ absent.

### Plot / element vocabulary

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| `plot` (line) | `Curve` | ✅ | `line_width`, `line_style` (4), `color`, `alpha` |
| `scatter` | `Scatter` | ✅ | `color`/`color_by`, `size`/`size_by`, `marker` (5), `alpha`; OpenGL + Datashader paths |
| `bar`/`barh` | `Bars` | ◑ | `orient` v/h, `group` (grouped); **no stacked bars**, no `bar_label` [gap] |
| `hist` | `Histogram` | ✅ | `bins`, `density` |
| `imshow` | `Image` | ✅ | `bounds`, `colormap`, `interpolation` (nearest/bilinear) |
| `pcolormesh`/heatmap | `Heatmap` | ◑ | tidy x/y/z pivot + aggregator; no irregular-mesh `pcolormesh`, no `pcolorfast` |
| `errorbar` | `ErrorBars` | ✅ | symmetric / `(lo,hi)`; direction x/y/both |
| `fill_between` (band) | `Spread` | ✅ | `y_lo`/`y_hi` confidence band |
| `step`/`stairs` | — | ❌ | no step/stairs element [gap] |
| `stackplot` / stacked area | — | ❌ | [gap] |
| `boxplot`/`bxp` | — | ❌ | core statistical type missing [gap] |
| `violinplot` | — | ❌ | [gap] |
| `hexbin` | — | ◑ | density covered by Datashader raster, but no hex binning [partial] |
| `ecdf` | — | ❌ | [gap] |
| `pie` | — | ❌ | [gap] |
| `eventplot` / raster | — | ❌ | [gap] |
| `stem` | — | ❌ | [gap] |
| `contour`/`contourf` | — | ❌ | no contouring; common scientific need [gap] |
| `quiver`/`streamplot`/`barbs` | — | ❌ | no vector-field elements [gap] |
| `tripcolor`/`triplot`/`tricontour` | — | ❌ | no unstructured-mesh support [gap] |
| `matshow`/`spy` | — | ◑ | `Image` covers dense matrices; no sparse `spy` |
| `hist2d` | — | ◑ | Datashader count-raster is the analog [partial] |
| spectral (`psd`/`specgram`/…) | — | ❌ | out of scope; do upstream then plot `Curve`/`Image` [non-goal] |
| `table` | — | ❌ | [gap, minor] |
| 3-D (`plot_surface`, …) | `RawFigure`→Plotly | ◑ | no **native** 3-D; webengine-only via passthrough [non-goal native] |
| network/graph drawing | — | ❌ | [gap] (HoloViews has `Graph`; adapter could map) |

### Axes, scales, ticks

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| log / symlog / logit / asinh scales | — | ❌ | **no axis transforms at all** — confirmed in `capabilities-gaps.md` §2; highest-impact gap for scientific/financial data [gap] |
| datetime axis (`matplotlib.dates`) | — | ❌ | no native time axis; webengine notes datetime "not wired" [gap] |
| custom locators / formatters | — | ❌ | no public tick-format/locator control (`EngFormatter`, `PercentFormatter`, date fmt) [gap] |
| custom projections (polar/geo) | — | ❌ | rectilinear only; polar/geo absent [gap, niche] |
| secondary axis (`secondary_xaxis`) | — | ❌ | [gap] |
| twin axes (`twinx`/`twiny`) | — | ❌ | no dual-y; common for engineering plots [gap] |
| shared axes (`sharex`/`sharey`) | `LayoutOptions.link_x/link_y` | ✅ | linked pan/zoom across panes — a qtviz strength |
| axis limits / inversion / aspect | ◑ via interaction | ◑ | pan/zoom set ranges; no declarative `xlim`/`ylim`/`aspect`/invert API [gap] |
| `axhline`/`axvline`/`axhspan` ref lines | — | ❌ | no reference lines/spans element [gap] |

### Styling, color, annotation

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| colormaps (named) | `colormap=` on Image/Heatmap, `palette` | ✅ | named colormaps + categorical palette |
| color normalization (`LogNorm`, `BoundaryNorm`, `TwoSlopeNorm`) | — | ❌ | only linear `Normalize` in the colorbar path; no log/diverging/discrete norms [gap] |
| legends | auto for `Scatter` `color_by` | ◑ | **no first-class legend element**; none for `Curve`/`Bars`; no multi-series overlay legend; none on Datashader rasters [gap] |
| colorbars | auto for continuous `color_by` (mpl) | ◑ | tied to Scatter color mapping; not standalone; not on rasters [gap] |
| `annotate` / arrows / `text` | — | ❌ | no annotation layer (callouts, labels, arrows) [gap] |
| `bar_label` / data labels | — | ❌ | [gap] |
| mathtext / LaTeX / usetex | — | ❌ | not exposed even on the mpl backend [gap, niche] |
| hatching / fill patterns / dash detail | line_style only | ◑ | 4 dash styles; no hatch, no custom dash, limited marker set (5) |
| rcParams / style sheets | `Theme` | ◑ | `Theme` is a small backend-agnostic surface (bg/fg/grid/palette/fonts); intentionally narrower than rcParams [non-goal] |
| title / axis labels | `OverlayOptions.title/x_label/y_label` | ✅ | present on the shared surface |

### Layout & figure composition

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| `subplots` grid | `Layout(kind="grid")` | ✅ | rows/cols/spacing |
| `subplot_mosaic` (spanning/nested) | — | ❌ | no cell spanning / mosaic / nested ragged layouts [gap] |
| splitter / tabs / dock panels | `Layout` kinds | ✅ | **beyond matplotlib** — real Qt splitter/tabs/dock |
| `subfigures` | nested `Layout` | ◑ | composition tree exists; not the same as independent subfigures |
| `constrained_layout`/`tight_layout` | Qt layout | ◑ | Qt does layout; no figure-level spacing-solver knobs |
| mixed-backend panes | `Layout` | ✅ | **beyond matplotlib** — pyqtgraph + mpl + web in one window |

### Output / export

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| PNG / SVG / PDF | `handle.export` (mpl backend) | ✅ | `savefig` PNG/SVG/PDF |
| PS / EPS / PGF | — | ❌ | LaTeX/PostScript export paths absent [gap, niche] |
| PNG raster (other backends) | pyqtgraph PNG, webengine PNG | ✅ | |
| composite / mixed-layout export | — | ❌ | `CompositeRenderHandle.export` raises; no single-surface export of a multi-pane layout [gap] |
| savefig options (dpi, bbox, transparent, metadata) | — | ◑ | `export(fmt, path)` only — no dpi/bbox/transparent/metadata knobs [gap] |

### Interaction & animation

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| pan / zoom | ✅ | ✅ | native, OpenGL-accelerated on pyqtgraph |
| pick / hover / tap | typed events | ✅ | `PickEvent`/`HoverEvent`/`TapEvent` |
| brush / box select | `SelectEvent` | ✅ | shift-drag brush → row indices/bounds |
| hover value on rasters | `HoverEvent.value` | ✅ | **beyond matplotlib** — count/mean under cursor on Datashader |
| selection back-map through raster | — | ❌ | pixel→source rows not done (blocks raster linked-brushing) [gap] |
| event system breadth | typed bus | ◑ | 5 typed events vs matplotlib's ~13 raw events; no key/scroll/resize/draw hooks exposed [partial] |
| widgets (sliders/selectors/cursor) | host Qt + `kdim_panel` | ◑ | use native Qt widgets; no built-in SpanSelector/Lasso/Cursor analogs [non-goal mostly] |
| animation (`FuncAnimation`) | reactive `Signal` re-render | ◑ | `View(Signal[Node])` drives updates, but no frame/timeline animation or movie export [gap] |

### Data & big-data

| matplotlib | qtviz | Status | Notes |
|---|---|---|---|
| in-memory arrays / pandas | ✅ | ✅ | dict/NumPy/pandas/Arrow eager |
| lazy / out-of-core | — (mpl has none) | ✅ | **beyond matplotlib** — Dask/xarray/zarr off-thread |
| big-data rasterization | — (needs datashader) | ✅ | **beyond matplotlib** — Datashader, viewport re-aggregation |
| derived channels | accessors/`Expression` | ✅ | **beyond matplotlib** — column/expr/callable/array, pushdown |
| datashader aggregators | count/mean/by(count) | ◑ | no sum/max/min/std/`by(mean)`/multi-agg `summary` [gap] |

## 2.2 The gaps that matter most

Filtering the matrix to genuine weaknesses (not non-goals), ranked by how much
real-world matplotlib usage they block:

1. **Axis transforms — log / symlog / datetime / custom ticks.** The single
   biggest gap. Scientific and financial data routinely need log axes and time
   axes; their absence forces users to pre-transform data and loses readable tick
   labels. Also gates Datashader `logx`/`logy`. *(Already #2 on qtviz's own
   priority list.)*

2. **Statistical element vocabulary — boxplot, violinplot, ecdf, (stacked bars),
   pie.** These are everyday analysis plots. HoloViews and seaborn have them;
   their absence is conspicuous for an analysis-facing library.

3. **Legends & colorbars as first-class, composable citizens.** Today only
   `Scatter.color_by` auto-emits a key. No legend for `Curve`/`Bars`, no
   multi-series overlay legend, nothing on Datashader rasters, no standalone
   colorbar, no color normalization (log/diverging/discrete). Blocks publishable
   multi-series and categorical/continuous raster figures.

4. **Annotation & reference layer — `annotate`, text, arrows, `axhline`/`axvline`,
   spans, data labels.** Almost every real figure has a threshold line, a callout,
   or labelled points. Currently impossible without dropping to a backend.

5. **Contour / vector-field / unstructured-mesh elements** (`contour`, `quiver`,
   `streamplot`, `tripcolor`). Core scientific 2-D types with no qtviz analog and
   no `RawFigure`-native path. (3-D is reasonably a `RawFigure`/Plotly non-goal;
   2-D contours are not.)

6. **Twin / secondary axes** (`twinx`, `secondary_xaxis`). Dual-y plots are a
   staple of engineering/telemetry dashboards — directly relevant to qtviz's target
   audience.

7. **Composite / mixed-layout export.** A multi-pane `Layout` can't export to a
   single surface (`CompositeRenderHandle.export` raises). For a tool whose pitch
   is "interact natively, then export for a report," this is a sharp edge.

8. **Datashader aggregation surface** (`sum`/`max`/`min`/`std`, `by(mean)`,
   `summary`) and raster legends/theming. Already tracked in
   `capabilities-gaps.md` §1.

9. **Animation / timeline.** Reactive signals cover *data-driven* updates but
   there's no frame/timeline animation or movie export (`FuncAnimation` analog).

10. **Export knobs** (dpi, `bbox_inches='tight'`, transparent, metadata) and
    additional vector formats (EPS/PS/PGF). Small but expected for publication use.

## 2.3 Where qtviz already exceeds matplotlib

Worth recording so the gap list isn't read as "qtviz is behind across the board":

- **Native-Qt, GPU-accelerated interaction** (pyqtgraph) — pan/zoom/brush at fps
  matplotlib can't reach for live/large data.
- **Out-of-core, lazy data + Datashader** with viewport re-aggregation and
  **hover-value on rasters** — matplotlib has none of this without bolting on the
  HoloViz stack.
- **One declarative, value-hashed `Element`** rendered across pyqtgraph / mpl /
  web, swappable at runtime — matplotlib is single-engine and imperative.
- **Mixed-backend layouts** and real Qt **splitter / tabs / dock** panels in one
  window — beyond matplotlib's figure model.
- **Functional data binding** (column / `Expression` / callable / array, with
  pushdown) and **reactive `Signal` re-render** / linked brushing without manual
  wiring.
- **Offline-by-design** including the web backend (bundled JS, no CDN).

## 2.4 Reading this against qtviz's strategy

matplotlib's breadth is its moat; qtviz's wedge is *interaction + big data +
offline + declarative-multi-backend*, with matplotlib used for export. So the
priority order above is filtered through that lens:

- **Close (table stakes):** axis transforms (#1), legends/colorbars (#3),
  annotation/reference lines (#4), twin/secondary axes (#6), composite export (#7),
  export knobs (#10) — these are expected of *any* serious plotting library and
  several are already on qtviz's roadmap.
- **Grow the vocabulary opportunistically:** boxplot/violin/ecdf/pie (#2),
  contour/quiver/tri (#5) — high value for the analysis/scientific audience; the
  HoloViews adapter is a natural forcing function (it already enumerates several of
  these), so vocabulary parity and adapter coverage can advance together.
- **Defensible non-goals (host Qt / `RawFigure` / upstream):** native 3-D, spectral
  transforms, the full rcParams surface, the matplotlib widget zoo, mathtext/LaTeX —
  reasonable to leave to `RawFigure`/Plotly, host Qt widgets, or upstream
  computation, **provided** the escape hatches stay frictionless.

---

## Sources

- matplotlib Axes API reference — https://matplotlib.org/stable/api/axes_api.html
- Plot-types gallery — https://matplotlib.org/stable/plot_types/index.html
- Release notes / What's new — https://matplotlib.org/stable/users/release_notes.html
- Axis scales — https://matplotlib.org/stable/users/explain/axes/axes_scales.html
- Colormap normalization — https://matplotlib.org/stable/users/explain/colors/colormapnorms.html
- Backends — https://matplotlib.org/stable/users/explain/figure/backends.html
- mplot3d — https://matplotlib.org/stable/api/toolkits/mplot3d/axes3d.html
- mpl source tree (Axes/Axes3D/widgets/animation/colors/scale) — https://github.com/matplotlib/matplotlib

qtviz capability facts are read directly from `src/qtviz/` (elements, core/options,
core/theme, core/view, backends/matplotlib, ext/datashader) and cross-checked
against [`capabilities-gaps.md`](capabilities-gaps.md), [`roadmap.md`](roadmap.md),
and [`../README.md`](../README.md) at the time of writing.
