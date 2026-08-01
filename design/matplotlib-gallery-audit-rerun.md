# The matplotlib gallery, re-audited — 507 examples after roadmap waves 1–3

> **Mandate (owner, 2026-07-31).** Re-run the gallery comparison and evaluate
> the current state of support — after the post-audit roadmap
> ([`roadmap-post-audit.md`](roadmap-post-audit.md), [D96]–[D110]) shipped all
> three waves: annotations & dressing (1.1), axis/tick control & raster norms
> (1.2), Mesh/Quiver & mosaic composition (1.3).
>
> **Method.** Same harness and verdict ladder as the
> [baseline audit](matplotlib-gallery-audit.md) (same day, pre-wave code).
> The baseline's 46 recreations were re-rendered unchanged (all still render —
> regression check), its 30 expected-failure probes re-fired (6 now *render*),
> and 26 new recreation cases were built against the shipped API for the
> examples the waves targeted, plus 4 residual probes proving what should
> still fail (symlog/boundary norms, curvilinear meshes, non-rectangular
> mosaics). All PNGs rendered offscreen on the matplotlib backend and
> inspected. Harness: session scratchpad `gallery_audit_v2/`
> (`recreate_v2.py`, `results_v2.json`).

## 0. Verdict legend

| Mark | Meaning |
|---|---|
| ✅ **full** | Recreated declaratively with the current API |
| ◑ **partial** | The chart's job is achievable, with stated caveats / upstream precompute / workarounds |
| 🔧 **escape** | Only via `handle.native()` / host-Qt / `RawFigure` (supported, non-portable) |
| ❌ **gap** | Not expressible — an in-scope hole worth knowing about |
| 🚫 **non-goal** | Out of scope by design ([D58]: 3-D, animation, widgets, rcParams, mpl embedding/internals) |
| 〰 **n/a** | Not a chart (docs/infra/introspection examples) |

## 1. Headline numbers — before → after

| | ✅ full | ◑ partial | 🔧 escape | ❌ gap | 🚫 non-goal | 〰 n/a |
|---|---|---|---|---|---|---|
| baseline (pre-wave) | 64 | 97 | 24 | 181 | 130 | 11 |
| **now** | **97** | **108** | **24** | **137** | **130** | **11** |
| share now | 19% | 21% | 5% | 27% | 26% | 2% |

56 examples moved up a rung. The three honest reads, before → after:

- **Of everything** (507): 161 → **205** (40%) achievable outright
  or with caveats; 24 more via escape hatches; 141
  non-goals/non-charts.
- **Of what qtviz considers in scope** (✅+◑+❌ = 342): 47% →
  **60% achievable** (205); gaps 181 → 137
  (40%).
- **Of the core chart categories** (lines/bars/markers, statistics,
  images/contours, pie, scales, subplots/axes): 92 → **117 of 161
  in-scope examples (73%)**.

The gallery's ❌ mass was concentrated in exactly the themes the roadmap
attacked — annotation machinery, tick control, shapes, grid composition,
meshes and vector fields — so a vocabulary of ~15 additions flipped
56 examples. What remains (§4) is dominated by genuinely-parked
subsystems (polar, triangulation, insets, the two mpl toolkits) rather than
scattered vocabulary holes.

## 2. Status of the defects the baseline audit discovered

All the code defects from the baseline's §2 were fixed the same day
(`fix(audit)` commit) or by the waves:

1. **P1 selector/autoscale corruption — fixed.** Time-series recreations
   (`date_axis`, `stock_prices`) re-render with correct autoscale; the
   selection artist no longer pollutes `dataLim`.
2. **`Histogram(alpha=)` — shipped.** Overlaid translucent histograms are
   first-class (re-verified: `v2_hist_alpha_overlay`).
3. **Colormap case sensitivity — fixed.** `colormap="greys"` renders on
   every backend (re-verified: `v2_colormap_case_insensitive`).
4. **Annotated-heatmap contrast — still open** (ergonomics backlog): per-cell
   `Text` needs a caller-chosen color; no per-cell luminance flip.
5. **`Text` vertical anchor — shipped** (`anchor_v=`); multi-line alignment
   nuance remains as-is.

New warts found by *this* re-run (small, worth queueing):

- **`Mesh` with 2-D edge arrays dies with a raw `TypeError`**
  (`only 0-dimensional arrays can be converted to Python scalars`) instead of
  a ValidationError saying curvilinear meshes aren't supported.
- `Quiver` has no `quiverkey` analog (a reference-magnitude legend), so
  calibrated vector fields lose their scale readout.

## 3. What flipped

Every verdict change from the baseline (56 total):


| example | was | now | how |
|---|---|---|---|
| `axline.py` | ❌ | ✅ | RefLine(slope, intercept) — warns-and-drops under log |
| `bar_colors.py` | ◑ | ✅ | Bars(color_by=) — per-bar categorical palette or continuous ramp |
| `bar_label_demo.py` | ❌ | ✅ | Bars(bar_labels='auto' or a format spec), outside/centered-in-stack |
| `broken_barh.py` | ❌ | ◑ | N filled Rects recreate the interval bars; no dedicated element |
| `fill.py` | ◑ | ✅ | Polygon(fill=True) draws arbitrary filled polygons |
| `fill_betweenx_demo.py` | ❌ | ✅ | Spread(y=, x_lo=, x_hi=) — the horizontal band |
| `horizontal_barchart_distribution.py` | ◑ | ✅ | stacked-h + centered in-segment bar_labels |
| `line_demo_dash_control.py` | ◑ | ✅ | line_style takes on/off dash tuples in points |
| `linestyles.py` | ◑ | ✅ | named styles + custom dash tuples |
| `markevery_demo.py` | ❌ | ◑ | marker_every=N covers the integer stride; list/fraction/slice forms not modeled |
| `multicolored_line.py` | ❌ | ✅ | Curve(color_by=continuous) → LineCollection ramp + colorbar (matplotlib; warns to solid elsewhere) |
| `scatter_star_poly.py` | ❌ | ◑ | star/pentagon/hexagon/plus shipped; arbitrary polygon/path glyphs still absent |
| `stem_plot.py` | ❌ | ✅ | `Stem(x=, y=, baseline=)` — one pair-connected polyline + head markers ([D115], wave 1.4) |
| `timeline.py` | ❌ | ✅ | `Stem` + leveled Text ([D115], wave 1.4) |
| `confidence_ellipse.py` | ❌ | ✅ | Scatter * Ellipse(angle=) — eigendecomposition upstream |
| `errorbars_and_boxes.py` | ❌ | ◑ | per-point filled Rects + ErrorBars compose it; no collection element |
| `barb_demo.py` | ❌ | ◑ | Quiver shows the field; wind-barb glyphs (flags/pennants) not modeled |
| `colormap_normalizations.py` | ❌ | ◑ | norm='log'/'power'/'symlog'/'boundary' ✓ ([D114], wave 1.4); two-slope not modeled |
| `image_nonuniform.py` | ❌ | ✅ | Mesh(values, x_edges=, y_edges=) |
| `irregulardatagrid.py` | ❌ | ◑ | Mesh covers the non-uniform-grid half; the triangulation half doesn't apply |
| `multi_image.py` | ◑ | ✅ | shared vmin=/vmax= give a common normalization across images |
| `pcolor_demo.py` | ❌ | ✅ | Mesh — non-uniform rectilinear cell edges |
| `pcolormesh_grids.py` | ❌ | ✅ | Mesh edge contract matches (flat shading; gouraud not modeled) |
| `pcolormesh_levels.py` | ❌ | ✅ | Mesh + norm='boundary' (levels=) — discrete colors, level-ticked colorbar ([D114], wave 1.4) |
| `quiver_demo.py` | ❌ | ✅ | Quiver ✓ (auto scale); `key=`/`key_label=` reference key as a legend entry ([D112], wave 1.4) |
| `quiver_simple_demo.py` | ❌ | ✅ | Quiver(x=, y=, u=, v=, arrow_scale=) |
| `power_norm.py` | ❌ | ✅ | Image/Heatmap/Mesh norm='power' + gamma= |
| `figure_title.py` | ◑ | ✅ | LayoutOptions(title=) suptitle + per-pane titles |
| `gridspec_customization.py` | ❌ | ✅ | Layout.mosaic + width_ratios/height_ratios |
| `gridspec_multicolumn.py` | ❌ | ✅ | Layout.mosaic spanning panes |
| `gridspec_nested.py` | ◑ | ✅ | nested Layouts + track ratios |
| `subfigures.py` | ❌ | ◑ | mosaic + nested Layouts with per-container titles approximate; no true subfigure machinery |
| `subplot2grid.py` | ❌ | ✅ | Layout.mosaic spanning panes |
| `auto_ticks.py` | ❌ | ◑ | explicit ticks= covers fixed positions; locator strategies not modeled |
| `custom_ticker1.py` | ◑ | ✅ | one-field templates or explicit ticks/tick_labels cover formatter callbacks' everyday job |
| `date_index_formatter.py` | ❌ | ✅ | explicit ticks= + tick_labels= skip the weekends |
| `dollar_ticks.py` | ❌ | ✅ | tick_format='${:,.0f}' one-field template |
| `major_minor_demo.py` | ❌ | ◑ | minor=True ✓; locator multiples not controllable |
| `tick_labels_from_values.py` | ❌ | ✅ | AxisSpec(ticks=, tick_labels=) |
| `ticklabels_rotation.py` | ❌ | ✅ | AxisSpec(tick_rotation=) (matplotlib+Plotly; pyqtgraph warns) |
| `color_by_yvalue.py` | ❌ | ✅ | Curve(color_by=) per-segment color |
| `annotation_basic.py` | ◑ | ✅ | Text + Arrow |
| `annotation_demo.py` | ❌ | ◑ | Arrow + Text cover plain callouts; fancy arrow styles/connection paths/boxes not modeled |
| `arrow_demo.py` | ❌ | ◑ | a grid of Arrows is expressible; the width/style zoo is not |
| `demo_text_rotation_mode.py` | ❌ | ✅ | Text(rotation=, anchor=, anchor_v=) |
| `fancytextbox_demo.py` | ❌ | ◑ | Text(frame=True) theme-styled box; the bbox style zoo not modeled |
| `text_alignment.py` | ◑ | ✅ | anchor= × anchor_v= — both axes |
| `text_rotation_relative_to_line.py` | ❌ | ◑ | static data-space rotation; screen-transform-tracking rotation not modeled |
| `stock_prices.py` | ◑ | ✅ | multi-curve + time axis + Text end-of-line labels (v1's P1 autoscale bug is fixed) |
| `hinton_demo.py` | ❌ | ◑ | per-cell sized filled Rects compose it; no collection element |
| `ishikawa_diagram.py` | ❌ | ◑ | Arrow/Polygon/Text can draw it as diagram art |
| `arrow_guide.py` | ❌ | ◑ | Arrow covers data-space arrows; the guide's transform variants don't apply |
| `ellipse_arrow.py` | ❌ | ✅ | Ellipse(angle=) + Arrow |
| `ellipse_collection.py` | ❌ | ◑ | N Ellipse elements; no collection with screen-unit sizing |
| `ellipse_demo.py` | ❌ | ✅ | Ellipse(cx, cy, rx, ry, angle=) |
| `fancybox_demo.py` | ❌ | ◑ | Text(frame=True)/Rect only; the fancy box style zoo not modeled |


## 4. The remaining ❌ gap mass, re-grouped (137 gaps)

Ranked by example count, with the standing scope call:

1. **The two mpl toolkits (~32)** — axes_grid1 (dividers, locatable axes,
   RGB composites, anchored artists) and axisartist (curvilinear/floating
   axes). Deep mpl machinery; no qtviz analog planned. Parked.
2. **Polar projection (~11)** — polar line/bar/scatter, radar, bullseye. The
   one whole projection still missing; §5-parked in the roadmap, demand-gated.
3. **Triangulation (~9)** — `tri*` contour/mesh/interp. A real scientific
   subsystem (triangulation + interpolation + hit-testing); parked.
4. **Axes composition tail (~10)** — insets/zoom connectors, broken axes,
   secondary transformed axes, >2 y-axes, margins/spacing knobs,
   figure-space text/legend ([D103] studied insets and parked them).
5. **Text/annotation long tail (~12)** — fancy arrow styles, styled box zoo,
   wrapped text, figure-space text, per-text fonts, custom legend handles,
   rainbow/path text. The everyday callout is covered; this is the styling
   zoo.
6. **Tick long tail (~6)** — locator strategies, label alignment,
   colorbar tick control, multi-level ticks, axis-side control.
7. **Norm tail (~3)** — symlog/boundary/two-slope norms (log/power shipped;
   probes prove these still fail cleanly except boundary, which needs a
   `levels=` vocabulary decision).
8. **Specialty diagrams (~8)** — Sankey, hillshading, hexbin geometry,
   skew-T, packed bubbles. RawFigure/escape territory; low priority.
9. **Collections/perf idioms (~5)** — event plots, per-point marker
   shape/rotation, screen-unit ellipse collections, gradient-filled bars.
10. **Misc mpl internals (~8)** — path effects, agg filters, SVG post-filters,
    artist transforms, multi-page PDF.

## 5. Where qtviz is *ahead* of the gallery

Unchanged from the baseline, plus one addition: `resample.py`'s zoom-driven
re-aggregation and `time_series_histogram.py`'s density trick remain
one-keyword built-ins; linked axes, backend switching, typed events,
streaming and out-of-core data come free with every multi-panel example; and
**streaming now composes with datashader** (wave 2-4) — a live density
raster re-aggregating on append is a pattern the gallery has no answer to at
all.

## 6. Per-category verdict (all 507 examples)


### Lines, bars and markers — 41 examples (✅ 23 · ◑ 11 · 🔧 2 · ❌ 5 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `axline.py` | ✅ | RefLine(slope, intercept) — warns-and-drops under log *(recreated: `v2:refline_axline`)* |
| `bar_colors.py` | ✅ | Bars(color_by=) — per-bar categorical palette or continuous ramp *(recreated: `v2:bars_per_bar_colors`)* |
| `bar_label_demo.py` | ✅ | Bars(bar_labels='auto' or a format spec), outside/centered-in-stack *(recreated: `v2:bar_labels_stacked`)* |
| `bar_stacked.py` | ✅ | Bars(mode='stacked') *(recreated: `stacked_bars`)* |
| `barchart.py` | ✅ | Bars(group=) *(recreated: `grouped_barchart`)* |
| `barh.py` | ✅ | Bars(orient='h') *(recreated: `barh`)* |
| `broken_barh.py` | ◑ | N filled Rects recreate the interval bars; no dedicated element *(recreated: `v2:broken_barh_rects`)* |
| `capstyle.py` | 🔧 | line cap styling — escape hatch |
| `categorical_variables.py` | ✅ | categorical x everywhere *(recreated: `grouped_barchart`)* |
| `eventcollection_demo.py` | ❌ | same *(probe: `PROBE_eventplot`)* |
| `eventplot_demo.py` | ❌ | no event/raster-tick element (probe) *(probe: `PROBE_eventplot`)* |
| `fill.py` | ✅ | Polygon(fill=True) draws arbitrary filled polygons *(recreated: `v2:filled_polygons`)* |
| `fill_between_alpha.py` | ✅ | Spread(alpha=) *(recreated: `fill_between_band`)* |
| `fill_between_demo.py` | ◑ | Spread ✓; where= conditional regions need NaN precompute *(recreated: `fill_between_band`)* |
| `fill_betweenx_demo.py` | ✅ | Spread(y=, x_lo=, x_hi=) — the horizontal band *(recreated: `v2:fill_betweenx`)* |
| `gradient_bar.py` | ❌ | image-filled bars (gradient fills) not modeled |
| `hat_graph.py` | ◑ | grouped bars + bar_labels ✓; the hat baseline-delta look needs precompute *(recreated: `v2:bar_labels`)* |
| `horizontal_barchart_distribution.py` | ✅ | stacked-h + centered in-segment bar_labels *(recreated: `v2:bar_labels`)* |
| `joinstyle.py` | 🔧 | line join styling — escape hatch |
| `line_demo_dash_control.py` | ✅ | line_style takes on/off dash tuples in points *(recreated: `v2:dash_tuples_markevery`)* |
| `lines_with_ticks_demo.py` | ❌ | ticked-stroke path effects not modeled |
| `linestyles.py` | ✅ | named styles + custom dash tuples *(recreated: `v2:dash_tuples_markevery`)* |
| `marker_reference.py` | ◑ | 10 of ~40 marker shapes (5 added in wave 1) *(recreated: `v2:new_markers`)* |
| `markevery_demo.py` | ◑ | marker_every=N covers the integer stride; list/fraction/slice forms not modeled *(recreated: `v2:dash_tuples_markevery`)* |
| `masked_demo.py` | ✅ | NaN masking breaks the line (connect='finite') *(recreated: `masked_nan_gaps`)* |
| `multicolored_line.py` | ✅ | Curve(color_by=continuous) → LineCollection ramp + colorbar (matplotlib; warns to solid elsewhere) *(recreated: `v2:multicolored_line`)* |
| `multivariate_marker_plot.py` | ❌ | per-point marker shape/rotation not modeled |
| `scatter_demo2.py` | ✅ | color_by + size_by *(recreated: `scatter_color_size`)* |
| `scatter_hist.py` | ◑ | grid panes; no axes-attached marginal histograms *(recreated: `scatter_hist_margins`)* |
| `scatter_masked.py` | ✅ | same via NaN rows *(recreated: `masked_nan_gaps`)* |
| `scatter_star_poly.py` | ◑ | star/pentagon/hexagon/plus shipped; arbitrary polygon/path glyphs still absent *(recreated: `v2:new_markers`)* |
| `scatter_with_legend.py` | ✅ | categorical color_by → auto key *(recreated: `scatter_with_legend`)* |
| `simple_plot.py` | ✅ | Curve + surface title/labels *(recreated: `simple_plot`)* |
| `span_regions.py` | ◑ | static Span ✓; condition-driven auto spans need precompute *(recreated: `hlines_vlines_spans`)* |
| `spectrum_demo.py` | ◑ | compute spectra upstream (numpy) → Curve; no spectral API by design *(recreated: `spectrum_upstream`)* |
| `stackplot_demo.py` | ✅ | Area(group=, mode='stacked') *(recreated: `stackplot`)* |
| `stairs_demo.py` | ✅ | Curve(step=) *(recreated: `step_stairs`)* |
| `stem_plot.py` | ✅ | `Stem(x=, y=, baseline=)` — one pair-connected polyline + head markers ([D115], wave 1.4) *(guard: `test_stem.py`)* |
| `step_demo.py` | ✅ | Curve(step='pre'/'mid'/'post') *(recreated: `step_stairs`)* |
| `timeline.py` | ✅ | `Stem` + leveled Text ([D115], wave 1.4) *(guard: `test_stem.py`)* |
| `vline_hline_demo.py` | ✅ | HLine/VLine/Span *(recreated: `hlines_vlines_spans`)* |

### Statistics — 28 examples (✅ 8 · ◑ 18 · 🔧 0 · ❌ 2 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `boxplot.py` | ◑ | BoxPlot ✓; whisker/cap/flier styling knobs not modeled *(recreated: `boxplots`)* |
| `boxplot_color.py` | ◑ | colors via by= palette; arbitrary per-box fills not modeled *(recreated: `boxplots`)* |
| `boxplot_demo.py` | ◑ | as boxplot.py *(recreated: `boxplots`)* |
| `boxplot_vs_violin.py` | ✅ | BoxPlot + Violin side by side *(recreated: `violin_vs_box`)* |
| `bxp.py` | ◑ | qtviz computes its own stats ([D67]); pre-computed bxp input not accepted *(recreated: `boxplots`)* |
| `cohere.py` | ◑ | upstream compute → Curve *(recreated: `spectrum_upstream`)* |
| `confidence_ellipse.py` | ✅ | Scatter * Ellipse(angle=) — eigendecomposition upstream *(recreated: `v2:confidence_ellipse`)* |
| `csd_demo.py` | ◑ | upstream compute → Curve *(recreated: `spectrum_upstream`)* |
| `curve_error_band.py` | ✅ | Spread + Curve *(recreated: `fill_between_band`)* |
| `customized_violin.py` | ◑ | quartile whisker overlays via extra elements only *(recreated: `violin_vs_box`)* |
| `errorbar.py` | ✅ | ErrorBars *(recreated: `errorbars`)* |
| `errorbar_features.py` | ✅ | asymmetric (lo,hi) + direction='both' *(recreated: `errorbars`)* |
| `errorbar_limits.py` | ❌ | lolims/uplims arrow caps not modeled (probe) *(probe: `PROBE_errorbar_limits_arrows`)* |
| `errorbar_limits_simple.py` | ❌ | same *(recreated: `errorbars`)* |
| `errorbar_subsample.py` | ◑ | errorevery= → subsample upstream *(recreated: `errorbars`)* |
| `errorbars_and_boxes.py` | ◑ | per-point filled Rects + ErrorBars compose it; no collection element *(recreated: `v2:broken_barh_rects`)* |
| `hexbin_demo.py` | ◑ | no hex binning (probe); the datashader raster covers the density job *(probe: `PROBE_hexbin`)* |
| `hist.py` | ✅ | Histogram (int + rule-string bins) *(recreated: `histograms`)* |
| `histogram_bihistogram.py` | ◑ | precompute negated counts → Bars |
| `histogram_cumulative.py` | ◑ | Ecdf covers the cumulative-density panel; cumulative counts precompute *(recreated: `hist_cumulative_ecdf`)* |
| `histogram_histtypes.py` | ◑ | one bar style; step/stepfilled histtypes not modeled |
| `histogram_multihist.py` | ◑ | Histogram(alpha=) is first-class now; step/stepfilled histtypes still absent *(recreated: `v2:hist_alpha_overlay`)* |
| `histogram_normalization.py` | ✅ | density=True; other norms precompute *(recreated: `histograms`)* |
| `multiple_histograms_side_by_side.py` | ◑ | Layout of Histograms; not interleaved on one axis *(recreated: `hist_overlaid`)* |
| `psd_demo.py` | ◑ | upstream compute → Curve (+ log axes) *(recreated: `spectrum_upstream`)* |
| `time_series_histogram.py` | ✅ | scale='datashader' is exactly this technique *(recreated: `time_series_density`)* |
| `violinplot.py` | ◑ | Violin ✓; means/extrema toggles + horizontal orientation not modeled *(recreated: `violin_vs_box`)* |
| `xcorr_acorr_demo.py` | ◑ | upstream compute; `Stem` now gives the native look ([D115]) *(recreated: `spectrum_upstream`)* |

### Images, contours and fields — 48 examples (✅ 12 · ◑ 16 · 🔧 2 · ❌ 17 · 🚫 1 · 〰 0)

| example | verdict | note |
|---|---|---|
| `affine_image.py` | ❌ | no artist transforms |
| `barb_demo.py` | ◑ | Quiver shows the field; wind-barb glyphs (flags/pennants) not modeled *(probe: `PROBE_quiver`)* |
| `barcode_demo.py` | ✅ | 1×N Image, nearest (colormap names case-insensitive since the v1 fix) *(recreated: `v2:colormap_case_insensitive`)* |
| `colormap_interactive_adjustment.py` | 🚫 | mpl-toolbar interaction; qtviz interaction is its own *(recreated: `colorbar_continuous`)* |
| `colormap_normalizations.py` | ◑ | norm='log'/'power'/'symlog'/'boundary' ✓ ([D114], wave 1.4); two-slope not modeled *(recreated: `v2:mesh_log_norm`; guard: `test_norms_tail.py`)* |
| `colormap_normalizations_symlognorm.py` | ✅ | norm='symlog' (linthresh=) — mpl's piecewise transform in core ([D114], wave 1.4) *(guard: `test_norms_tail.py`)* |
| `contour_corner_mask.py` | ❌ | corner_mask rendering control |
| `contour_demo.py` | ✅ | Contour(levels=) *(recreated: `contours`)* |
| `contour_image.py` | ✅ | Image * Contour overlay *(recreated: `contours`)* |
| `contour_label_demo.py` | ❌ | no inline level labels (clabel) |
| `contourf_demo.py` | ✅ | Contour(filled=True) + colorbar *(recreated: `contours`)* |
| `contourf_hatching.py` | ❌ | no hatching anywhere *(probe: `PROBE_hatching`)* |
| `contourf_log.py` | ◑ | explicit level values ✓; log-spaced levels computable upstream, raster norm='log'/'symlog' now covers the shading half ([D114]) *(recreated: `contours`)* |
| `contours_in_optimization_demo.py` | ✅ | Contour + Curve/Scatter overlay *(recreated: `contours`)* |
| `demo_bboximage.py` | 🔧 | figure-space images — escape hatch |
| `figimage_demo.py` | 🔧 | same |
| `image_annotated_heatmap.py` | ✅ | `Heatmap(cell_labels=)` — core-computed per-cell contrast (WCAG luminance → theme fg/bg), ~400-cell guard ([D113], wave 1.4) *(recreated: `annotated_heatmap`; guard: `test_heatmap_cell_labels.py`)* |
| `image_antialiasing.py` | ◑ | nearest/bilinear only *(recreated: `image_interpolation`)* |
| `image_clip_path.py` | ❌ | no clip paths |
| `image_demo.py` | ✅ | Image(bounds=, colormap=) *(recreated: `image_basic`)* |
| `image_exact_placement.py` | ◑ | data-space bounds ✓; pixel-exact figure placement not modeled *(recreated: `image_basic`)* |
| `image_masked.py` | ◑ | NaN cells render blank; interactive range clipping not modeled |
| `image_nonuniform.py` | ✅ | Mesh(values, x_edges=, y_edges=) *(recreated: `v2:mesh_nonuniform`)* |
| `image_transparency_blend.py` | ◑ | precompute RGBA; Image has no alpha=/norm *(recreated: `layered_images_rgba`)* |
| `image_zcoord.py` | ◑ | hover value exists on datashaded rasters only (HoverEvent.value) |
| `interpolation_methods.py` | ◑ | 2 of ~18 interpolation modes *(recreated: `image_interpolation`)* |
| `irregulardatagrid.py` | ◑ | Mesh covers the non-uniform-grid half; the triangulation half doesn't apply *(recreated: `v2:mesh_nonuniform`)* |
| `layer_images.py` | ◑ | overlay two Images; blending via precomputed RGBA only *(recreated: `layered_images_rgba`)* |
| `matshow.py` | ✅ | Image *(recreated: `image_basic`)* |
| `multi_image.py` | ✅ | shared vmin=/vmax= give a common normalization across images *(recreated: `v2:shared_norm_images`)* |
| `pcolor_demo.py` | ✅ | Mesh — non-uniform rectilinear cell edges *(recreated: `v2:mesh_nonuniform`)* |
| `pcolormesh_grids.py` | ✅ | Mesh edge contract matches (flat shading; gouraud not modeled) *(recreated: `v2:mesh_nonuniform`)* |
| `pcolormesh_levels.py` | ✅ | Mesh + norm='boundary' (levels=) — discrete colors, level-ticked colorbar ([D114], wave 1.4) *(guard: `test_norms_tail.py`)* |
| `plot_streamplot.py` | ❌ | no streamlines (probe) *(probe: `PROBE_streamplot`)* |
| `quadmesh_demo.py` | ❌ | curvilinear (2-D coordinate) meshes not modeled (probe — fails with a raw TypeError, a validation wart) *(probe: `v2:PROBE_curvilinear_mesh`)* |
| `quiver_demo.py` | ✅ | Quiver ✓ (auto scale); `key=`/`key_label=` reference key as a legend entry ([D112], wave 1.4) *(recreated: `v2:quiver_field`; key guard: `test_quiver.py`)* |
| `quiver_simple_demo.py` | ✅ | Quiver(x=, y=, u=, v=, arrow_scale=) *(recreated: `v2:quiver_field`)* |
| `shading_example.py` | ❌ | no hillshading/light sources |
| `specgram_demo.py` | ◑ | compute spectrogram upstream → Image *(recreated: `spectrum_upstream`)* |
| `spy_demos.py` | ◑ | boolean Image approximates spy *(recreated: `barcode_spy`)* |
| `tricontour_demo.py` | ❌ | no triangulated data (probe) *(probe: `PROBE_tricontour`)* |
| `tricontour_smooth_delaunay.py` | ❌ | same |
| `tricontour_smooth_user.py` | ❌ | same |
| `trigradient_demo.py` | ❌ | same |
| `triinterp_demo.py` | ❌ | same |
| `tripcolor_demo.py` | ❌ | same *(probe: `PROBE_tricontour`)* |
| `triplot_demo.py` | ❌ | same *(probe: `PROBE_tricontour`)* |
| `watermark_image.py` | ❌ | figure-level watermark not modeled |

### Pie and polar charts — 10 examples (✅ 1 · ◑ 2 · 🔧 0 · ❌ 7 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `bar_of_pie.py` | ❌ | pie-to-bar connectors are patch art |
| `nested_pie.py` | ❌ | no multi-ring pies |
| `pie_and_donut_labels.py` | ◑ | hole ✓; wedge annotations/autopct not modeled *(recreated: `pie_donut`)* |
| `pie_features.py` | ◑ | Pie ✓; explode/shadow/autopct not modeled *(recreated: `pie_donut`)* |
| `pie_label.py` | ✅ | Pie(labels=) *(recreated: `pie_donut`)* |
| `polar_bar.py` | ❌ | no polar projection ([D83] tail) *(probe: `PROBE_polar`)* |
| `polar_demo.py` | ❌ | no polar projection ([D83] tail) *(probe: `PROBE_polar`)* |
| `polar_error_caps.py` | ❌ | no polar projection ([D83] tail) *(probe: `PROBE_polar`)* |
| `polar_legend.py` | ❌ | no polar projection ([D83] tail) *(probe: `PROBE_polar`)* |
| `polar_scatter.py` | ❌ | no polar projection ([D83] tail) *(probe: `PROBE_polar`)* |

### Scales — 8 examples (✅ 3 · ◑ 2 · 🔧 0 · ❌ 3 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `asinh_demo.py` | ❌ | asinh scale not in vocabulary (probe: ValidationError) *(probe: `PROBE_asinh_logit_scales`)* |
| `aspect_loglog.py` | ◑ | aspect + log both exist; adjustable-box semantics differ *(recreated: `log_scales`)* |
| `custom_scale.py` | ❌ | no custom scale registration *(probe: `PROBE_asinh_logit_scales`)* |
| `log_demo.py` | ✅ | AxisSpec(scale='log') per axis *(recreated: `log_scales`)* |
| `logit_demo.py` | ❌ | logit scale not in vocabulary *(probe: `PROBE_asinh_logit_scales`)* |
| `power_norm.py` | ✅ | Image/Heatmap/Mesh norm='power' + gamma= *(recreated: `v2:raster_norms`)* |
| `scales.py` | ◑ | linear/log/symlog/time of mpl's 7+ *(recreated: `log_scales`)* |
| `symlog_demo.py` | ✅ | scale='symlog' (matplotlib backend) *(recreated: `symlog`)* |

### Subplots, axes and figures — 36 examples (✅ 15 · ◑ 6 · 🔧 0 · ❌ 10 · 🚫 5 · 〰 0)

| example | verdict | note |
|---|---|---|
| `align_labels_demo.py` | ◑ | grid ✓; label alignment automatic-only *(recreated: `subplot_grids`)* |
| `auto_subplots_adjust.py` | 🚫 | mpl layout internals |
| `axes_box_aspect.py` | ◑ | data aspect only; box aspect not modeled *(recreated: `invert_and_aspect`)* |
| `axes_demo.py` | ❌ | axes-inside-axes inset |
| `axes_margins.py` | ❌ | no margin/sticky-edge control |
| `axes_props.py` | ◑ | grid toggle ✓; spine/tick styling via theme only |
| `axes_zoom_effect.py` | ❌ | no inset/zoom connectors *(probe: `PROBE_inset_zoom`)* |
| `axhspan_demo.py` | ✅ | Span *(recreated: `hlines_vlines_spans`)* |
| `axis_equal_demo.py` | ✅ | OverlayOptions(aspect=1) *(recreated: `invert_and_aspect`)* |
| `axis_labels_demo.py` | ✅ | x_label/y_label |
| `broken_axis.py` | ❌ | no broken axes |
| `custom_figure_class.py` | 🚫 | mpl Figure subclassing |
| `demo_constrained_layout.py` | 🚫 | layout-engine knobs (Qt lays out panes) |
| `demo_tight_layout.py` | 🚫 | same |
| `fahrenheit_celsius_scales.py` | ❌ | same *(probe: `PROBE_secondary_units_axis`)* |
| `figure_size_units.py` | 🚫 | figure sizing = Qt widget sizing |
| `figure_title.py` | ✅ | LayoutOptions(title=) suptitle + per-pane titles *(recreated: `v2:suptitle`)* |
| `ganged_plots.py` | ◑ | linked ✓; zero-gap ganging not modeled *(recreated: `subplot_grids`)* |
| `geo_demo.py` | ❌ | no geographic projections |
| `gridspec_and_subplots.py` | ✅ | uniform Layout grid *(recreated: `subplot_grids`)* |
| `gridspec_customization.py` | ✅ | Layout.mosaic + width_ratios/height_ratios *(recreated: `v2:mosaic_spans_ratios`)* |
| `gridspec_multicolumn.py` | ✅ | Layout.mosaic spanning panes *(recreated: `v2:mosaic_spans_ratios`)* |
| `gridspec_nested.py` | ✅ | nested Layouts + track ratios *(recreated: `v2:mosaic_spans_ratios`)* |
| `invert_axes.py` | ✅ | AxisSpec(invert=True) *(recreated: `invert_and_aspect`)* |
| `multiple_figs_demo.py` | ✅ | multiple Views |
| `multiple_yaxis_with_spines.py` | ❌ | only one twin axis (probe: y3 rejected) *(probe: `PROBE_third_y_axis`)* |
| `secondary_axis.py` | ❌ | no transformed secondary axes (probe) *(probe: `PROBE_secondary_units_axis`)* |
| `shared_axis_demo.py` | ✅ | LayoutOptions(link_x=True) *(recreated: `subplot_grids`)* |
| `subfigures.py` | ◑ | mosaic + nested Layouts with per-container titles approximate; no true subfigure machinery *(probe: `PROBE_gridspec_span`)* |
| `subplot.py` | ✅ | Layout(cols=1) *(recreated: `subplot_grids`)* |
| `subplot2grid.py` | ✅ | Layout.mosaic spanning panes *(recreated: `v2:mosaic_spans_ratios`)* |
| `subplots_adjust.py` | ❌ | no spacing knobs on the single-figure grid |
| `subplots_demo.py` | ✅ | Layout grids + link_x/link_y *(recreated: `subplot_grids`)* |
| `twin_axes_zorder.py` | ◑ | y2 ✓; draw-order control not modeled |
| `two_scales.py` | ✅ | axis='y2' + OverlayOptions(y2=) *(recreated: `twin_axes`)* |
| `zoom_inset_axes.py` | ❌ | no inset axes (probe) *(probe: `PROBE_inset_zoom`)* |

### Ticks — 25 examples (✅ 8 · ◑ 10 · 🔧 0 · ❌ 6 · 🚫 0 · 〰 1)

| example | verdict | note |
|---|---|---|
| `align_ticklabels.py` | ❌ | no tick label alignment |
| `auto_ticks.py` | ◑ | explicit ticks= covers fixed positions; locator strategies not modeled *(recreated: `v2:minor_ticks_rotation`)* |
| `centered_ticklabels.py` | ❌ | same |
| `colorbar_tick_labelling_demo.py` | ❌ | no colorbar tick control |
| `custom_ticker1.py` | ✅ | one-field templates or explicit ticks/tick_labels cover formatter callbacks' everyday job *(recreated: `v2:ticks_explicit_labels`)* |
| `date.py` | ✅ | datetime64 → calendar-aligned ticks (the v1 P1 autoscale bug is fixed) *(recreated: `date_axis`)* |
| `date_concise_formatter.py` | ◑ | span-adaptive auto format ✓; concise offset style not modeled *(recreated: `date_axis`)* |
| `date_demo_convert.py` | ✅ | datetime64 columns *(recreated: `date_axis`)* |
| `date_demo_rrule.py` | ◑ | same *(recreated: `date_strftime_format`)* |
| `date_formatters_locators.py` | ◑ | strftime tick_format ✓; locator control not modeled *(recreated: `date_strftime_format`)* |
| `date_index_formatter.py` | ✅ | explicit ticks= + tick_labels= skip the weekends *(recreated: `v2:ticks_explicit_labels`)* |
| `date_precision_and_epochs.py` | ◑ | ns-precision ✓; epoch control is a non-need (epoch-seconds canonical) *(recreated: `date_axis`)* |
| `dollar_ticks.py` | ✅ | tick_format='${:,.0f}' one-field template *(recreated: `v2:dollar_template_ticks`)* |
| `engformatter_offset.py` | ◑ | eng ✓; offset notation not modeled |
| `engineering_formatter.py` | ✅ | tick_format='eng' *(recreated: `eng_and_percent_formatters`)* |
| `fig_axes_customize_simple.py` | ◑ | theme colors cover most of it |
| `major_minor_demo.py` | ◑ | minor=True ✓; locator multiples not controllable *(recreated: `v2:minor_ticks_rotation`)* |
| `multilevel_ticks.py` | ❌ | no grouped/multi-level ticks *(probe: `PROBE_minor_ticks`)* |
| `scalarformatter.py` | ◑ | format specs ✓; sci-notation offsets not modeled *(recreated: `eng_and_percent_formatters`)* |
| `tick-formatters.py` | ◑ | spec/eng/strftime/template subset of mpl's formatter zoo |
| `tick-locators.py` | ❌ | no locator control *(probe: `PROBE_minor_ticks`)* |
| `tick_labels_from_values.py` | ✅ | AxisSpec(ticks=, tick_labels=) *(recreated: `v2:ticks_explicit_labels`)* |
| `ticklabels_rotation.py` | ✅ | AxisSpec(tick_rotation=) (matplotlib+Plotly; pyqtgraph warns) *(recreated: `v2:minor_ticks_rotation`)* |
| `ticks_too_many.py` | 〰 | perf-pitfall doc |
| `ticks_top_right.py` | ❌ | no axis-side control |

### Color — 11 examples (✅ 4 · ◑ 3 · 🔧 0 · ❌ 3 · 🚫 0 · 〰 1)

| example | verdict | note |
|---|---|---|
| `color_by_yvalue.py` | ✅ | Curve(color_by=) per-segment color *(recreated: `v2:multicolored_line`)* |
| `color_cycle_default.py` | ✅ | palette cycling by series slot *(recreated: `custom_palette_cycle`)* |
| `color_demo.py` | ✅ | ColorSpec everywhere *(recreated: `custom_palette_cycle`)* |
| `color_sequences.py` | ◑ | custom Palette.from_hex for categorical cycles *(recreated: `custom_palette_cycle`)* |
| `colorbar_basics.py` | ◑ | automatic colorbars only; no standalone/extend controls *(recreated: `colorbar_continuous`)* |
| `colorbar_histogram.py` | ❌ | colorbar-as-histogram composition |
| `colormap_reference.py` | ◑ | render ramps as Images; no registry browse |
| `custom_cmap.py` | ❌ | no custom continuous colormaps for color_by (probe: fixed viridis) *(probe: `PROBE_custom_continuous_cmap`)* |
| `individual_colors_from_cmap.py` | ❌ | no cmap sampling API (use any hex directly) *(probe: `PROBE_custom_continuous_cmap`)* |
| `named_colors.py` | 〰 | a color-name chart of mpl's registry |
| `set_alpha.py` | ✅ | alpha= / 8-digit hex |

### Text, labels and annotations — 43 examples (✅ 7 · ◑ 14 · 🔧 0 · ❌ 16 · 🚫 3 · 〰 3)

| example | verdict | note |
|---|---|---|
| `accented_text.py` | ✅ | unicode text everywhere |
| `angle_annotation.py` | ❌ | arc/angle annotations *(probe: `PROBE_annotate_arrow`)* |
| `angles_on_bracket_arrows.py` | ❌ | bracket arrows |
| `annotation_basic.py` | ✅ | Text + Arrow *(recreated: `v2:annotate_arrow`)* |
| `annotation_demo.py` | ◑ | Arrow + Text cover plain callouts; fancy arrow styles/connection paths/boxes not modeled *(recreated: `v2:annotate_arrow`)* |
| `annotation_polar.py` | ❌ | polar + arrows *(probe: `PROBE_polar`)* |
| `arrow_demo.py` | ◑ | a grid of Arrows is expressible; the width/style zoo is not *(probe: `PROBE_annotate_arrow`)* |
| `autowrap.py` | ❌ | no text wrapping |
| `custom_legends.py` | ❌ | no manual legend handles |
| `demo_annotation_box.py` | ❌ | offset/annotation boxes |
| `demo_text_path.py` | ❌ | text-as-path effects |
| `demo_text_rotation_mode.py` | ✅ | Text(rotation=, anchor=, anchor_v=) *(recreated: `v2:text_rotation_frame`)* |
| `dfrac_demo.py` | ◑ | same |
| `fancyarrow_demo.py` | ❌ | arrow style zoo *(probe: `PROBE_annotate_arrow`)* |
| `fancytextbox_demo.py` | ◑ | Text(frame=True) theme-styled box; the bbox style zoo not modeled |
| `figlegend_demo.py` | ❌ | no figure-level legend |
| `font_family_rc.py` | ◑ | Theme(font_family=) exists but is not applied on the mpl backend (known wart) |
| `font_file.py` | ❌ | load font files |
| `font_table.py` | 〰 | font browser |
| `fonts_demo.py` | ❌ | per-text font families/weights |
| `fonts_demo_kw.py` | ❌ | same |
| `label_subplots.py` | ✅ | per-pane titles *(recreated: `titles_labels_legend`)* |
| `legend.py` | ✅ | label= + legend aggregation *(recreated: `titles_labels_legend`)* |
| `legend_demo.py` | ◑ | placement/multi-column/custom handlers not modeled *(recreated: `titles_labels_legend`)* |
| `line_with_text.py` | ◑ | Curve * Text; text doesn't track the artist |
| `mathtext_asarray.py` | 〰 | mathtext to array |
| `mathtext_demo.py` | ◑ | $…$ renders via mpl only — incidental, not portable |
| `mathtext_examples.py` | ◑ | same |
| `mathtext_fontfamily_example.py` | ❌ | mathtext font control |
| `multiline.py` | ✅ | Text with newlines *(recreated: `text_notes`)* |
| `placing_text_boxes.py` | ◑ | frame=True box ✓; axes-fraction coordinates still absent *(recreated: `v2:text_rotation_frame`)* |
| `rainbow_text.py` | ❌ | multi-color rich text |
| `stix_fonts_demo.py` | ❌ | math font selection |
| `tex_demo.py` | 🚫 | usetex/LaTeX |
| `text_alignment.py` | ✅ | anchor= × anchor_v= — both axes *(recreated: `text_notes`)* |
| `text_commands.py` | ◑ | titles/labels/Text/suptitle ✓; figtext not modeled *(recreated: `v2:suptitle`)* |
| `text_fontdict.py` | ◑ | size/color only; family/weight per-text not modeled |
| `text_rotation_relative_to_line.py` | ◑ | static data-space rotation; screen-transform-tracking rotation not modeled *(recreated: `v2:text_rotation_frame`)* |
| `titles_demo.py` | ◑ | title ✓; left/right title placement not modeled *(recreated: `titles_labels_legend`)* |
| `unicode_minus.py` | 〰 | rc detail |
| `usetex_baseline_test.py` | 🚫 | same |
| `usetex_fonteffects.py` | 🚫 | same |
| `watermark_text.py` | ❌ | figure-space text |

### Style sheets — 8 examples (✅ 1 · ◑ 7 · 🔧 0 · ❌ 0 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `bmh.py` | ◑ | Theme(background/foreground/grid/palette/fonts) approximates the look; no rcParams style system |
| `dark_background.py` | ✅ | Theme.dark() *(recreated: `theme_dark_style`)* |
| `fivethirtyeight.py` | ◑ | Theme(background/foreground/grid/palette/fonts) approximates the look; no rcParams style system |
| `ggplot.py` | ◑ | Theme(background/foreground/grid/palette/fonts) approximates the look; no rcParams style system |
| `grayscale.py` | ◑ | Theme(background/foreground/grid/palette/fonts) approximates the look; no rcParams style system |
| `petroff10.py` | ◑ | Theme(background/foreground/grid/palette/fonts) approximates the look; no rcParams style system |
| `plot_solarizedlight2.py` | ◑ | Theme(background/foreground/grid/palette/fonts) approximates the look; no rcParams style system |
| `style_sheets_reference.py` | ◑ | Theme covers colors/palette; not the full rc surface *(recreated: `theme_dark_style`)* |

### Showcase — 7 examples (✅ 2 · ◑ 2 · 🔧 1 · ❌ 0 · 🚫 2 · 〰 0)

| example | verdict | note |
|---|---|---|
| `anatomy.py` | 🚫 | a matplotlib-anatomy teaching figure |
| `firefox.py` | 🔧 | SVG-path art — escape hatch |
| `integral.py` | ◑ | Area over a sub-range + Text ✓; mathtext annotation + polygon shading approximated |
| `mandelbrot.py` | ✅ | computed grid → Image(norm='power', gamma=) — the shading now matches *(recreated: `mandelbrot_image`)* |
| `pan_zoom_overlap.py` | ◑ | overlapping-axes gesture routing is mpl-specific; qtviz panes don't overlap |
| `stock_prices.py` | ✅ | multi-curve + time axis + Text end-of-line labels (v1's P1 autoscale bug is fixed) *(recreated: `stock_prices`)* |
| `xkcd.py` | 🚫 | xkcd sketch style |

### Specialty plots — 12 examples (✅ 1 · ◑ 3 · 🔧 0 · ❌ 8 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `advanced_hillshading.py` | ❌ | hillshading/light sources |
| `anscombe.py` | ✅ | 2×2 linked grid of Scatters *(recreated: `anscombe_quartet`)* |
| `hinton_demo.py` | ◑ | per-cell sized filled Rects compose it; no collection element |
| `ishikawa_diagram.py` | ◑ | Arrow/Polygon/Text can draw it as diagram art |
| `leftventricle_bullseye.py` | ❌ | polar mesh |
| `mri_with_eeg.py` | ◑ | stacked linked panels ✓; shared-y strip layout differs *(recreated: `mri_with_eeg_panels`)* |
| `radar_chart.py` | ❌ | polar projection *(probe: `PROBE_polar`)* |
| `sankey_basics.py` | ❌ | no Sankey (probe); RawFigure+Plotly can host one *(probe: `PROBE_sankey`)* |
| `sankey_links.py` | ❌ | same *(probe: `PROBE_sankey`)* |
| `sankey_rankine.py` | ❌ | same *(probe: `PROBE_sankey`)* |
| `skewt.py` | ❌ | custom skewed projection |
| `topographic_hillshading.py` | ❌ | same |

### Shapes and collections — 18 examples (✅ 3 · ◑ 3 · 🔧 9 · ❌ 3 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `arrow_guide.py` | ◑ | Arrow covers data-space arrows; the guide's transform variants don't apply |
| `artist_reference.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `collections.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `compound_path.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `dolphin.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `donut.py` | 🔧 | path-construction demo (Pie(hole=) covers donut charts) *(recreated: `pie_donut`)* |
| `ellipse_arrow.py` | ✅ | Ellipse(angle=) + Arrow *(recreated: `v2:confidence_ellipse`)* |
| `ellipse_collection.py` | ◑ | N Ellipse elements; no collection with screen-unit sizing |
| `ellipse_demo.py` | ✅ | Ellipse(cx, cy, rx, ry, angle=) *(recreated: `v2:confidence_ellipse`)* |
| `fancybox_demo.py` | ◑ | Text(frame=True)/Rect only; the fancy box style zoo not modeled |
| `hatch_demo.py` | ❌ | no hatching (probe) *(probe: `PROBE_hatching`)* |
| `hatch_style_reference.py` | ❌ | same *(probe: `PROBE_hatching`)* |
| `hatchcolor_demo.py` | ❌ | same |
| `line_collection.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `patch_collection.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `path_patch.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `quad_bezier.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `scatter.py` | ✅ | Scatter *(recreated: `scatter_color_size`)* |

### Spines — 4 examples (✅ 0 · ◑ 0 · 🔧 4 · ❌ 0 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `centered_spines_with_arrows.py` | 🔧 | spine placement/visibility — handle.axes[i].spines escape hatch |
| `spine_placement_demo.py` | 🔧 | spine placement/visibility — handle.axes[i].spines escape hatch |
| `spines.py` | 🔧 | spine placement/visibility — handle.axes[i].spines escape hatch |
| `spines_dropped.py` | 🔧 | spine placement/visibility — handle.axes[i].spines escape hatch |

### pyplot — 2 examples (✅ 2 · ◑ 0 · 🔧 0 · ❌ 0 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `pyplot_simple.py` | ✅ | Curve *(recreated: `simple_plot`)* |
| `pyplot_two_subplots.py` | ✅ | Layout(cols=1) *(recreated: `subplot_grids`)* |

### Event handling — 21 examples (✅ 1 · ◑ 6 · 🔧 3 · ❌ 8 · 🚫 3 · 〰 0)

| example | verdict | note |
|---|---|---|
| `close_event.py` | 🚫 | Qt widget lifecycle |
| `coords_demo.py` | ◑ | HoverEvent carries data-space coords |
| `cursor_demo.py` | 🔧 | crosshair via handle.native() (example 33) |
| `data_browser.py` | ◑ | PickEvent + Signal-driven detail panel (the crossfilter pattern) |
| `figure_axes_enter_leave.py` | ❌ | enter/leave events not typed |
| `ginput_manual_clabel_sgskip.py` | ❌ | blocking input |
| `image_slices_viewer.py` | 🔧 | scroll-wheel paging via host Qt |
| `keypress_demo.py` | 🔧 | key bindings via host Qt shortcuts |
| `lasso_demo.py` | ❌ | rectangular brush only — no lasso/polygon selection |
| `legend_picking.py` | ❌ | legends are not interactive |
| `looking_glass.py` | ❌ | draggable clip regions |
| `path_editor.py` | ❌ | vertex editing |
| `pick_event_demo.py` | ◑ | PickEvent covers artist picking for data elements |
| `pick_event_demo2.py` | ◑ | PickEvent + reactive re-render |
| `poly_editor.py` | ❌ | same |
| `pong_sgskip.py` | 🚫 | a game |
| `resample.py` | ✅ | viewport-driven re-aggregation is built in (datashader/regrid) |
| `timers.py` | 🚫 | Qt timers |
| `trifinder_event_demo.py` | ❌ | triangulation hit-testing |
| `viewlims.py` | ◑ | RangeEvent + set_root recompute-on-zoom |
| `zoom_window.py` | ◑ | linked views / RangeEvent |

### Units — 10 examples (✅ 0 · ◑ 0 · 🔧 0 · ❌ 0 · 🚫 10 · 〰 0)

All 10 examples: 🚫 — mpl's unit-framework machinery; qtviz treats units as upstream data prep (datetime64 is the one built-in unit type).

<details><summary>File list</summary>

- `annotate_with_units.py`
- `artist_tests.py`
- `bar_demo2.py`
- `bar_unit_demo.py`
- `basic_units.py`
- `ellipse_with_units.py`
- `evans_test.py`
- `radian_demo.py`
- `units_sample.py`
- `units_scatter.py`

</details>


### axes_grid1 toolkit — 23 examples (✅ 2 · ◑ 3 · 🔧 0 · ❌ 18 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `demo_anchored_direction_arrows.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_axes_divider.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_axes_grid.py` | ◑ | same |
| `demo_axes_grid2.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_axes_hbox_divider.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_axes_rgb.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_colorbar_with_axes_divider.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_colorbar_with_inset_locator.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_edge_colorbar.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_fixed_size_axes.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `demo_imagegrid_aspect.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `inset_locator_demo.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog *(probe: `PROBE_inset_zoom`)* |
| `inset_locator_demo2.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog *(probe: `PROBE_inset_zoom`)* |
| `make_room_for_ylabel_using_axesgrid.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `parasite_simple.py` | ✅ | axis='y2' *(recreated: `twin_axes`)* |
| `parasite_simple2.py` | ❌ | multiple parasite axes (only one y2) |
| `scatter_hist_locatable_axes.py` | ◑ | separate panes; not size-locked marginals *(recreated: `scatter_hist_margins`)* |
| `simple_anchored_artists.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `simple_axes_divider1.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `simple_axes_divider3.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |
| `simple_axesgrid.py` | ✅ | uniform Layout grid of Images |
| `simple_axesgrid2.py` | ◑ | grid ✓ + shared vmin/vmax normalization; single shared colorbar not modeled |
| `simple_axisline4.py` | ❌ | axes_grid1 toolkit (dividers, insets, RGB composites, anchored artists) has no qtviz analog |

### axisartist toolkit — 17 examples (✅ 1 · ◑ 0 · 🔧 0 · ❌ 16 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `axis_direction.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_axis_direction.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_axisline_style.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_curvelinear_grid.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_curvelinear_grid2.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_floating_axes.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_floating_axis.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_parasite_axes.py` | ✅ | axis='y2' *(recreated: `twin_axes`)* |
| `demo_parasite_axes2.py` | ❌ | three y axes |
| `demo_ticklabel_alignment.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `demo_ticklabel_direction.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `simple_axis_direction01.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `simple_axis_direction03.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `simple_axis_pad.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `simple_axisartist1.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `simple_axisline.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |
| `simple_axisline3.py` | ❌ | axisartist toolkit (curvilinear grids, floating/rotated axes, per-axis art) has no qtviz analog |

### Miscellaneous — 30 examples (✅ 3 · ◑ 2 · 🔧 3 · ❌ 15 · 🚫 1 · 〰 6)

| example | verdict | note |
|---|---|---|
| `anchored_artists.py` | ❌ | anchored boxes/sizebars |
| `bbox_intersect.py` | 〰 | geometry utility |
| `contour_manual.py` | ❌ | manual contour segments |
| `coords_report.py` | ◑ | HoverEvent |
| `custom_projection.py` | ❌ | projection framework |
| `customize_rc.py` | 🚫 | rcParams styling |
| `demo_agg_filter.py` | ❌ | agg image filters |
| `demo_ribbon_box.py` | ❌ | image-stretched boxes |
| `fig_x.py` | 🔧 | figure-space lines |
| `fill_spiral.py` | ❌ | polygon art *(recreated: `v2:filled_polygons`)* |
| `findobj_demo.py` | 〰 | artist introspection |
| `font_indexing.py` | 〰 | font internals |
| `ftface_props.py` | 〰 | font internals |
| `histogram_path.py` | 🔧 | path-built histogram — Histogram covers the chart |
| `hyperlinks_sgskip.py` | ❌ | SVG hyperlinks |
| `keyword_plotting.py` | ✅ | data-first API is qtviz's default shape |
| `logos2.py` | 🔧 | logo art |
| `multipage_pdf.py` | ❌ | no multi-page PDF export |
| `multiprocess_sgskip.py` | ✅ | qv.stream appends from any thread/process feed |
| `packed_bubbles.py` | ❌ | bubble-packing chart |
| `patheffect_demo.py` | ❌ | path effects (glow/shadow) |
| `print_stdout_sgskip.py` | 〰 | print backend |
| `rasterization_demo.py` | ✅ | Scatter(matplotlib_rasterized=True) |
| `set_and_get.py` | 〰 | artist get/set tour |
| `svg_filter_line.py` | ❌ | SVG post-filters |
| `svg_filter_pie.py` | ❌ | same |
| `table_demo.py` | ❌ | no table element (host Qt has real tables) |
| `tickedstroke_demo.py` | ❌ | ticked strokes |
| `transoffset.py` | ❌ | offset transforms (points-space offsets) not modeled |
| `zorder_demo.py` | ◑ | draw order = Overlay child order; no numeric zorder |

### Animation — 15 examples (✅ 0 · ◑ 0 · 🔧 0 · ❌ 0 · 🚫 15 · 〰 0)

All 15 examples: 🚫 — frame/timeline animation is a standing non-goal ([D58]); streaming + reactive Signals cover data-driven updates.

<details><summary>File list</summary>

- `animate_decay.py`
- `animated_histogram.py`
- `animation_demo.py`
- `bayes_update.py`
- `double_pendulum.py`
- `dynamic_image.py`
- `frame_grabbing_sgskip.py`
- `multiple_axes.py`
- `pause_resume.py`
- `rain.py`
- `random_walk.py`
- `simple_anim.py`
- `simple_scatter.py`
- `strip_chart.py`
- `unchained.py`

</details>


### 3D plotting (mplot3d) — 47 examples (✅ 0 · ◑ 0 · 🔧 0 · ❌ 0 · 🚫 47 · 〰 0)

All 47 examples: 🚫 — native 3-D is a standing non-goal ([D58]); the supported path is RawFigure + Plotly (example 18).

<details><summary>File list</summary>

- `2dcollections3d.py`
- `3d_bars.py`
- `axlim_clip.py`
- `bars3d.py`
- `box3d.py`
- `contour3d.py`
- `contour3d_2.py`
- `contour3d_3.py`
- `contourf3d.py`
- `contourf3d_2.py`
- `custom_shaded_3d_surface.py`
- `errorbar3d.py`
- `fillbetween3d.py`
- `fillunder3d.py`
- `hist3d.py`
- `imshow3d.py`
- `intersecting_planes.py`
- `lines3d.py`
- `lorenz_attractor.py`
- `mixed_subplots.py`
- `offset.py`
- `pathpatch3d.py`
- `polys3d.py`
- `projections.py`
- `quiver3d.py`
- `rotate_axes3d_sgskip.py`
- `scales3d.py`
- `scatter3d.py`
- `stem3d_demo.py`
- `subplot3d.py`
- `surface3d.py`
- `surface3d_2.py`
- `surface3d_3.py`
- `surface3d_radial.py`
- `text3d.py`
- `tricontour3d.py`
- `tricontourf3d.py`
- `trisurf3d.py`
- `trisurf3d_2.py`
- `view_planes_3d.py`
- `voxels.py`
- `voxels_numpy_logo.py`
- `voxels_rgb.py`
- `voxels_torus.py`
- `wire3d.py`
- `wire3d_animation.py`
- `wire3d_zero_stride.py`

</details>


### Widgets — 18 examples (✅ 0 · ◑ 0 · 🔧 0 · ❌ 0 · 🚫 18 · 〰 0)

All 18 examples: 🚫 — mpl's widget zoo is a non-goal — the host app uses real Qt widgets (sliders/buttons) driving Signals.

<details><summary>File list</summary>

- `annotated_cursor.py`
- `buttons.py`
- `check_buttons.py`
- `cursor.py`
- `lasso_selector_demo_sgskip.py`
- `menu.py`
- `mouse_cursor.py`
- `multicursor.py`
- `polygon_selector_demo.py`
- `polygon_selector_simple.py`
- `radio_buttons.py`
- `radio_buttons_grid.py`
- `range_slider.py`
- `rectangle_selector.py`
- `slider_demo.py`
- `slider_snap_demo.py`
- `span_selector.py`
- `textbox.py`

</details>


### Embedding in GUIs (user_interfaces) — 25 examples (✅ 0 · ◑ 0 · 🔧 0 · ❌ 0 · 🚫 25 · 〰 0)

All 25 examples: 🚫 — embedding demos — qtviz IS the Qt embedding; a View is already a QWidget.

<details><summary>File list</summary>

- `canvasagg.py`
- `embedding_in_gtk3_panzoom_sgskip.py`
- `embedding_in_gtk3_sgskip.py`
- `embedding_in_gtk4_panzoom_sgskip.py`
- `embedding_in_gtk4_sgskip.py`
- `embedding_in_qt_sgskip.py`
- `embedding_in_tk_sgskip.py`
- `embedding_in_wx2_sgskip.py`
- `embedding_in_wx3_sgskip.py`
- `embedding_in_wx4_sgskip.py`
- `embedding_in_wx5_sgskip.py`
- `embedding_webagg_sgskip.py`
- `fourier_demo_wx_sgskip.py`
- `gtk3_spreadsheet_sgskip.py`
- `gtk4_spreadsheet_sgskip.py`
- `mathtext_wx_sgskip.py`
- `mpl_with_glade3_sgskip.py`
- `mplcvd.py`
- `pylab_with_gtk3_sgskip.py`
- `pylab_with_gtk4_sgskip.py`
- `svg_histogram_sgskip.py`
- `svg_tooltip_sgskip.py`
- `toolmanager_sgskip.py`
- `web_application_server_sgskip.py`
- `wxcursor_demo_sgskip.py`

</details>



## 7. Summary — the state of qtviz against the matplotlib gallery, after the waves

The baseline audit's closing line was "the chart types are substantially
there — the figure dressing is not." The three waves were aimed at exactly
that dressing, and the re-run confirms they landed: **60% of in-scope
gallery examples are now achievable** (was 47%), and in the core chart
categories it is **73%** (was 57%). The single biggest baseline
themes — annotation machinery, tick control, shapes, grid composition — are
now covered at their everyday-90% level; meshes and vector fields went from
absent to first-class elements; raster norms and shared normalization closed
the scientific-imaging basics.

What the 137 remaining gaps have in common is that they are *systems*,
not vocabulary: polar (the one missing projection), triangulation, insets,
the two mpl toolkits, and the styling zoos (fancy arrows/boxes, locator
strategies, path effects). Every one of them is either §5-parked in the
roadmap by explicit decision or routed to `RawFigure`/escape hatches. The
re-run found **almost no accidental holes left in scope** — the residue that
is neither parked nor escape-routed is small and named: inline contour
labels (`clabel`), streamplot, errorbar limit arrows, an eventplot/stem
element, and the §2 warts queued above.

Practical residue for the backlog, in priority order:

1. **Mesh 2-D-edges error message** — raw TypeError should be a
   ValidationError naming the curvilinear limitation (smallest item here).
2. **`quiverkey` analog** — calibrated vector fields need a magnitude legend.
3. **Boundary/symlog norms** — the only remaining scientific-imaging norms;
   `norm='boundary'` needs a `levels=` vocabulary decision first.
4. **Annotated-heatmap per-cell contrast** — the one baseline §2 wart still
   open.
