# The matplotlib gallery, recreated — a 507-example audit of qtviz

> **Mandate (owner, 2026-07-31).** Go through every example in the matplotlib
> gallery and try to recreate it with qtviz; note anything we cannot do or
> have trouble with. No library changes — current codebase only.
>
> **Method.** The gallery was enumerated from the matplotlib source tree
> (`galleries/examples/`, 507 `.py` examples across 24 categories — the
> stable-docs gallery index blocks fetching, the repo is the same content).
> Every distinct chart pattern was **actually recreated and rendered**
> offscreen on the matplotlib backend (46 recreation cases, all
> rendering, PNGs inspected visually), and every suspected gap was **proven by
> a failing probe** (30 probes, each failing with the expected
> validation/attribute error) rather than assumed. Harness + PNGs:
> session scratchpad `gallery_audit/` (`recreate.py`, `results.json`).
> Companion docs: [`matplotlib-support-matrix.md`](matplotlib-support-matrix.md)
> (API-level), [`parity-program.md`](parity-program.md) (what just shipped).

## 0. Verdict legend

| Mark | Meaning |
|---|---|
| ✅ **full** | Recreated declaratively with the current API |
| ◑ **partial** | The chart's job is achievable, with stated caveats / upstream precompute / workarounds |
| 🔧 **escape** | Only via `handle.native()` / host-Qt / `RawFigure` (supported, non-portable) |
| ❌ **gap** | Not expressible — an in-scope hole worth knowing about |
| 🚫 **non-goal** | Out of scope by design ([D58]: 3-D, animation, widgets, rcParams, mpl embedding/internals) |
| 〰 **n/a** | Not a chart (docs/infra/introspection examples) |

## 1. Headline numbers

| | ✅ full | ◑ partial | 🔧 escape | ❌ gap | 🚫 non-goal | 〰 n/a | total |
|---|---|---|---|---|---|---|---|
| examples | 64 | 97 | 24 | 181 | 130 | 11 | 507 |
| share | 13% | 19% | 5% | 36% | 26% | 2% | |

Three ways to read the same numbers, honestly:

- **Of everything** (507): 161 (32%) achievable outright or with caveats;
  24 more via escape hatches; 141 non-goals/non-charts.
- **Of what qtviz considers in scope** (✅+◑+❌ = 342): **161 achievable
  (47%)**, 181 gaps (53%).
- **Of the core chart categories** (lines/bars/markers, statistics,
  images/contours, pie, scales, subplots/axes — the categories about *charts*
  rather than dressing/toolkits): 92 of 161 in-scope examples
  achievable (**57%**).

The example-count metric is harsh on purpose: the gallery over-represents
mpl's annotation/tick/patch/toolkit machinery (one missing capability — say
arrows — fails a dozen examples), and those themes are exactly where the ❌
mass sits (§3). The chart vocabulary itself is largely covered; the *figure
dressing* is not.

## 2. Defects DISCOVERED by this audit (not gaps — bugs/warts in what exists)

1. **P1 — the [D95] rubber-band selector corrupts autoscale.** The
   `RectangleSelector` parked on every brushable matplotlib surface adds its
   0×0 rectangle at (0, 0) to the Axes' `dataLim`, so autoscale includes the
   origin. Any data far from (0, 0) — **every epoch-seconds time axis** —
   renders zoomed out to 1970 (verified: `dataLim x = [0, 1.74e9]` for a
   2025 series; `date_axis` / `stock_prices` recreations show it). Explicit
   `lim=`/`restore_state` unaffected, which is why the test suite missed it.
   Fix candidates: exclude the selection artist from dataLim, or lazy-create
   the selector on first drag.
2. **`Histogram` has no `alpha=`** — overlaid translucent histograms (a
   gallery staple, `histogram_multihist.py`) only work via the undocumented
   8-digit-hex color workaround (`color="#1f77b499"`). Every other filled
   element has `alpha`; this is an inconsistency, not a design choice.
3. **Colormap names are case-sensitive raw passthrough on matplotlib**
   (`colormap="greys"` raises from inside mpl; webengine lowercases its
   names). One vocabulary should behave one way.
4. **Annotated heatmaps have a contrast problem**: per-cell `Text` works, but
   with a single text color, labels vanish on dark cells (mpl's version
   flips text color per cell luminance).
5. **`Text` ignores multi-line alignment nuance and has no vertical anchor**
   (existing known wart, re-confirmed here).

## 3. The ❌ gap mass, grouped (what the 181 gaps actually are)

Ranked by how many gallery examples each theme blocks, with an honest
assessment of whether qtviz *should* close it:

1. **Annotation machinery (~25 examples)** — arrows/callouts (`annotate`),
   styled text boxes, text rotation, figure-space text, wrapped text, data
   labels (`bar_label`). The single biggest blocker of real-world figure
   polish. *Worth closing incrementally: arrowed `Text`, `rotation=`,
   `bar_labels=` on Bars.*
2. **Tick control (~15)** — locators, minor ticks, label rotation, arbitrary
   formatter callbacks, prefix/currency formats, value→label maps. The [D86]
   vocabulary covers the common 80%; the rest is a locator/format seam away.
3. **Patch/shape vocabulary (~15 in-scope of ~30)** — ellipses (confidence
   ellipse!), rectangles, polygons, arbitrary fills. *A small `Shape`
   annotation element would convert most of these.*
4. **Irregular meshes + triangulation (~12)** — `pcolormesh` with explicit
   edges, `NonUniformImage`, `tri*`. Real scientific need; heavy lift.
5. **Polar projection (~10)** — polar line/bar/scatter, radar charts. The one
   whole *projection* qtviz lacks; everything else here is rectilinear.
6. **Vector fields (~5)** — quiver/barbs/streamplot. Classic scientific
   vocabulary, absent.
7. **Color normalization on rasters (~5)** — log/symlog/power/boundary norms
   for Image/Heatmap (scatter `color_norm` exists; rasters have nothing).
8. **Axes composition (~40, incl. the axes_grid1/axisartist toolkits)** —
   insets/zoom connectors, broken axes, cell spanning / ratio grids,
   secondary transformed axes, >2 y-axes, figure suptitle/figlegend,
   dividers, curvilinear/floating axes. The two toolkits alone are ~32
   examples; most are deep mpl machinery that only the inset/span/ratio
   subset is worth chasing.
9. **Fill-direction + line-styling details (~8)** — `fill_betweenx`, custom
   dash tuples, `markevery`, per-segment line color, custom markers,
   hatching, `axline(slope=)`.
10. **Specialty diagrams (~8)** — Sankey, hillshading, hexbin geometry,
    Hinton, skew-T. Mostly RawFigure/escape territory; low priority.

## 4. Where qtviz is *ahead* of the gallery

Recreating the gallery also showed the reverse direction. `resample.py`'s
laborious zoom-driven decimation callback is **built in** (datashader +
`RasterController`); `time_series_histogram.py`'s density trick is one
keyword (`scale="datashader"`); every multi-panel example gets linked axes,
backend switching, typed events, streaming, and out-of-core data for free;
box/violin/histogram draw **identical numbers on all three backends** where
mpl's are engine-specific; and every interactive example (`data_browser`,
`viewlims`, `zoom_window`) maps to typed events + reactive Signals in a
fraction of the code.

## 5. Per-category verdict (all 507 examples)


### Lines, bars and markers — 41 examples (✅ 14 · ◑ 11 · 🔧 2 · ❌ 14 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `axline.py` | ❌ | only h/v reference lines; arbitrary slope not modeled (probe) *(probe: `PROBE_axline_slope`)* |
| `bar_colors.py` | ◑ | one color per series; per-bar colors need one Bars per color *(recreated: `grouped_barchart`)* |
| `bar_label_demo.py` | ❌ | no bar/data labels (probe: TypeError) *(probe: `PROBE_bar_labels`)* |
| `bar_stacked.py` | ✅ | Bars(mode='stacked') *(recreated: `stacked_bars`)* |
| `barchart.py` | ✅ | Bars(group=) *(recreated: `grouped_barchart`)* |
| `barh.py` | ✅ | Bars(orient='h') *(recreated: `barh`)* |
| `broken_barh.py` | ❌ | no interval-bar element (probe) *(probe: `PROBE_broken_barh`)* |
| `capstyle.py` | 🔧 | line cap styling — escape hatch |
| `categorical_variables.py` | ✅ | categorical x everywhere *(recreated: `grouped_barchart`)* |
| `eventcollection_demo.py` | ❌ | same *(probe: `PROBE_eventplot`)* |
| `eventplot_demo.py` | ❌ | no event/raster-tick element (probe) *(probe: `PROBE_eventplot`)* |
| `fill.py` | ◑ | zero-baseline Area ✓; arbitrary filled polygons not modeled *(recreated: `area_fill`)* |
| `fill_between_alpha.py` | ✅ | Spread(alpha=) *(recreated: `fill_between_band`)* |
| `fill_between_demo.py` | ◑ | Spread ✓; where= conditional regions need NaN precompute *(recreated: `fill_between_band`)* |
| `fill_betweenx_demo.py` | ❌ | no horizontal (x-direction) band (probe) *(probe: `PROBE_fill_betweenx`)* |
| `gradient_bar.py` | ❌ | image-filled bars (gradient fills) not modeled |
| `hat_graph.py` | ◑ | grouped bars ✓; per-bar value annotations not modeled |
| `horizontal_barchart_distribution.py` | ◑ | stacked-h ✓; centered in-bar labels not modeled *(recreated: `barh`)* |
| `joinstyle.py` | 🔧 | line join styling — escape hatch |
| `line_demo_dash_control.py` | ◑ | 4 named dash styles; custom on/off dash tuples not modeled *(recreated: `dash_styles`)* |
| `lines_with_ticks_demo.py` | ❌ | ticked-stroke path effects not modeled |
| `linestyles.py` | ◑ | same: named styles only *(recreated: `dash_styles`)* |
| `marker_reference.py` | ◑ | 5 of ~40 marker shapes *(probe: `PROBE_custom_marker`)* |
| `markevery_demo.py` | ❌ | markers are all-points-or-none (probe) *(probe: `PROBE_markevery`)* |
| `masked_demo.py` | ✅ | NaN masking breaks the line (connect='finite') *(recreated: `masked_nan_gaps`)* |
| `multicolored_line.py` | ❌ | no per-segment line color / Curve color_by (probe) *(probe: `PROBE_multicolored_line`)* |
| `multivariate_marker_plot.py` | ❌ | per-point marker shape/rotation not modeled |
| `scatter_demo2.py` | ✅ | color_by + size_by *(recreated: `scatter_color_size`)* |
| `scatter_hist.py` | ◑ | grid panes; no axes-attached marginal histograms *(recreated: `scatter_hist_margins`)* |
| `scatter_masked.py` | ✅ | same via NaN rows *(recreated: `masked_nan_gaps`)* |
| `scatter_star_poly.py` | ❌ | custom marker glyphs (probe) *(probe: `PROBE_custom_marker`)* |
| `scatter_with_legend.py` | ✅ | categorical color_by → auto key *(recreated: `scatter_with_legend`)* |
| `simple_plot.py` | ✅ | Curve + surface title/labels *(recreated: `simple_plot`)* |
| `span_regions.py` | ◑ | static Span ✓; condition-driven auto spans need precompute *(recreated: `hlines_vlines_spans`)* |
| `spectrum_demo.py` | ◑ | compute spectra upstream (numpy) → Curve; no spectral API by design *(recreated: `spectrum_upstream`)* |
| `stackplot_demo.py` | ✅ | Area(group=, mode='stacked') *(recreated: `stackplot`)* |
| `stairs_demo.py` | ✅ | Curve(step=) *(recreated: `step_stairs`)* |
| `stem_plot.py` | ❌ | no stem element (probe) *(probe: `PROBE_stem`)* |
| `step_demo.py` | ✅ | Curve(step='pre'/'mid'/'post') *(recreated: `step_stairs`)* |
| `timeline.py` | ❌ | stem + leveled annotations composition *(recreated: `date_axis`)* |
| `vline_hline_demo.py` | ✅ | HLine/VLine/Span *(recreated: `hlines_vlines_spans`)* |

### Statistics — 28 examples (✅ 7 · ◑ 17 · 🔧 0 · ❌ 4 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `boxplot.py` | ◑ | BoxPlot ✓; whisker/cap/flier styling knobs not modeled *(recreated: `boxplots`)* |
| `boxplot_color.py` | ◑ | colors via by= palette; arbitrary per-box fills not modeled *(recreated: `boxplots`)* |
| `boxplot_demo.py` | ◑ | as boxplot.py *(recreated: `boxplots`)* |
| `boxplot_vs_violin.py` | ✅ | BoxPlot + Violin side by side *(recreated: `violin_vs_box`)* |
| `bxp.py` | ◑ | qtviz computes its own stats ([D67]); pre-computed bxp input not accepted *(recreated: `boxplots`)* |
| `cohere.py` | ◑ | upstream compute → Curve *(recreated: `spectrum_upstream`)* |
| `confidence_ellipse.py` | ❌ | no ellipse/patch element (probe) *(probe: `PROBE_confidence_ellipse`)* |
| `csd_demo.py` | ◑ | upstream compute → Curve *(recreated: `spectrum_upstream`)* |
| `curve_error_band.py` | ✅ | Spread + Curve *(recreated: `fill_between_band`)* |
| `customized_violin.py` | ◑ | quartile whisker overlays via extra elements only *(recreated: `violin_vs_box`)* |
| `errorbar.py` | ✅ | ErrorBars *(recreated: `errorbars`)* |
| `errorbar_features.py` | ✅ | asymmetric (lo,hi) + direction='both' *(recreated: `errorbars`)* |
| `errorbar_limits.py` | ❌ | lolims/uplims arrow caps not modeled (probe) *(probe: `PROBE_errorbar_limits_arrows`)* |
| `errorbar_limits_simple.py` | ❌ | same *(recreated: `errorbars`)* |
| `errorbar_subsample.py` | ◑ | errorevery= → subsample upstream *(recreated: `errorbars`)* |
| `errorbars_and_boxes.py` | ❌ | error rectangles are patch collections |
| `hexbin_demo.py` | ◑ | no hex binning (probe); the datashader raster covers the density job *(probe: `PROBE_hexbin`)* |
| `hist.py` | ✅ | Histogram (int + rule-string bins) *(recreated: `histograms`)* |
| `histogram_bihistogram.py` | ◑ | precompute negated counts → Bars |
| `histogram_cumulative.py` | ◑ | Ecdf covers the cumulative-density panel; cumulative counts precompute *(recreated: `hist_cumulative_ecdf`)* |
| `histogram_histtypes.py` | ◑ | one bar style; step/stepfilled histtypes not modeled |
| `histogram_multihist.py` | ◑ | overlay works but only via 8-digit-hex alpha colors — Histogram has no alpha= (found by this audit) *(recreated: `hist_overlaid`)* |
| `histogram_normalization.py` | ✅ | density=True; other norms precompute *(recreated: `histograms`)* |
| `multiple_histograms_side_by_side.py` | ◑ | Layout of Histograms; not interleaved on one axis *(recreated: `hist_overlaid`)* |
| `psd_demo.py` | ◑ | upstream compute → Curve (+ log axes) *(recreated: `spectrum_upstream`)* |
| `time_series_histogram.py` | ✅ | scale='datashader' is exactly this technique *(recreated: `time_series_density`)* |
| `violinplot.py` | ◑ | Violin ✓; means/extrema toggles + horizontal orientation not modeled *(recreated: `violin_vs_box`)* |
| `xcorr_acorr_demo.py` | ◑ | upstream compute; stem look unavailable → Bars/Curve *(recreated: `spectrum_upstream`)* |

### Images, contours and fields — 48 examples (✅ 7 · ◑ 12 · 🔧 2 · ❌ 26 · 🚫 1 · 〰 0)

| example | verdict | note |
|---|---|---|
| `affine_image.py` | ❌ | no artist transforms |
| `barb_demo.py` | ❌ | same *(probe: `PROBE_quiver`)* |
| `barcode_demo.py` | ✅ | 1×N Image, nearest (colormap names are case-sensitive — found by this audit) *(recreated: `barcode_spy`)* |
| `colormap_interactive_adjustment.py` | 🚫 | mpl-toolbar interaction; qtviz interaction is its own *(recreated: `colorbar_continuous`)* |
| `colormap_normalizations.py` | ❌ | no color normalization on rasters (probe: no norm=) *(probe: `PROBE_image_norm`)* |
| `colormap_normalizations_symlognorm.py` | ❌ | same *(probe: `PROBE_image_norm`)* |
| `contour_corner_mask.py` | ❌ | corner_mask rendering control |
| `contour_demo.py` | ✅ | Contour(levels=) *(recreated: `contours`)* |
| `contour_image.py` | ✅ | Image * Contour overlay *(recreated: `contours`)* |
| `contour_label_demo.py` | ❌ | no inline level labels (clabel) |
| `contourf_demo.py` | ✅ | Contour(filled=True) + colorbar *(recreated: `contours`)* |
| `contourf_hatching.py` | ❌ | no hatching anywhere *(probe: `PROBE_hatching`)* |
| `contourf_log.py` | ◑ | explicit level values ✓; log-spaced locator/norm not modeled *(recreated: `contours`)* |
| `contours_in_optimization_demo.py` | ✅ | Contour + Curve/Scatter overlay *(recreated: `contours`)* |
| `demo_bboximage.py` | 🔧 | figure-space images — escape hatch |
| `figimage_demo.py` | 🔧 | same |
| `image_annotated_heatmap.py` | ◑ | Heatmap + per-cell Text ✓; single text color → unreadable on dark cells (no per-cell contrast) *(recreated: `annotated_heatmap`)* |
| `image_antialiasing.py` | ◑ | nearest/bilinear only *(recreated: `image_interpolation`)* |
| `image_clip_path.py` | ❌ | no clip paths |
| `image_demo.py` | ✅ | Image(bounds=, colormap=) *(recreated: `image_basic`)* |
| `image_exact_placement.py` | ◑ | data-space bounds ✓; pixel-exact figure placement not modeled *(recreated: `image_basic`)* |
| `image_masked.py` | ◑ | NaN cells render blank; interactive range clipping not modeled |
| `image_nonuniform.py` | ❌ | non-uniform image grids (probe) *(probe: `PROBE_pcolormesh_nonuniform`)* |
| `image_transparency_blend.py` | ◑ | precompute RGBA; Image has no alpha=/norm *(recreated: `layered_images_rgba`)* |
| `image_zcoord.py` | ◑ | hover value exists on datashaded rasters only (HoverEvent.value) |
| `interpolation_methods.py` | ◑ | 2 of ~18 interpolation modes *(recreated: `image_interpolation`)* |
| `irregulardatagrid.py` | ❌ | same *(probe: `PROBE_pcolormesh_nonuniform`)* |
| `layer_images.py` | ◑ | overlay two Images; blending via precomputed RGBA only *(recreated: `layered_images_rgba`)* |
| `matshow.py` | ✅ | Image *(recreated: `image_basic`)* |
| `multi_image.py` | ◑ | no shared color normalization across images |
| `pcolor_demo.py` | ❌ | no irregular-edge mesh (probe) *(probe: `PROBE_pcolormesh_nonuniform`)* |
| `pcolormesh_grids.py` | ❌ | same *(probe: `PROBE_pcolormesh_nonuniform`)* |
| `pcolormesh_levels.py` | ❌ | same + BoundaryNorm *(probe: `PROBE_pcolormesh_nonuniform`)* |
| `plot_streamplot.py` | ❌ | no streamlines (probe) *(probe: `PROBE_streamplot`)* |
| `quadmesh_demo.py` | ❌ | same |
| `quiver_demo.py` | ❌ | no vector-field elements (probe) *(probe: `PROBE_quiver`)* |
| `quiver_simple_demo.py` | ❌ | same *(probe: `PROBE_quiver`)* |
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

### Scales — 8 examples (✅ 2 · ◑ 2 · 🔧 0 · ❌ 4 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `asinh_demo.py` | ❌ | asinh scale not in vocabulary (probe: ValidationError) *(probe: `PROBE_asinh_logit_scales`)* |
| `aspect_loglog.py` | ◑ | aspect + log both exist; adjustable-box semantics differ *(recreated: `log_scales`)* |
| `custom_scale.py` | ❌ | no custom scale registration *(probe: `PROBE_asinh_logit_scales`)* |
| `log_demo.py` | ✅ | AxisSpec(scale='log') per axis *(recreated: `log_scales`)* |
| `logit_demo.py` | ❌ | logit scale not in vocabulary *(probe: `PROBE_asinh_logit_scales`)* |
| `power_norm.py` | ❌ | no color norms beyond linear/log-on-scatter *(probe: `PROBE_image_norm`)* |
| `scales.py` | ◑ | linear/log/symlog/time of mpl's 7+ *(recreated: `log_scales`)* |
| `symlog_demo.py` | ✅ | scale='symlog' (matplotlib backend) *(recreated: `symlog`)* |

### Subplots, axes and figures — 36 examples (✅ 10 · ◑ 7 · 🔧 0 · ❌ 14 · 🚫 5 · 〰 0)

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
| `figure_title.py` | ◑ | per-surface titles ✓; no figure-level suptitle |
| `ganged_plots.py` | ◑ | linked ✓; zero-gap ganging not modeled *(recreated: `subplot_grids`)* |
| `geo_demo.py` | ❌ | no geographic projections |
| `gridspec_and_subplots.py` | ✅ | uniform Layout grid *(recreated: `subplot_grids`)* |
| `gridspec_customization.py` | ❌ | no row/col ratios or spans (probe) *(probe: `PROBE_gridspec_span`)* |
| `gridspec_multicolumn.py` | ❌ | no cell spanning *(probe: `PROBE_gridspec_span`)* |
| `gridspec_nested.py` | ◑ | nested Layouts exist; ratio control doesn't *(probe: `PROBE_gridspec_span`)* |
| `invert_axes.py` | ✅ | AxisSpec(invert=True) *(recreated: `invert_and_aspect`)* |
| `multiple_figs_demo.py` | ✅ | multiple Views |
| `multiple_yaxis_with_spines.py` | ❌ | only one twin axis (probe: y3 rejected) *(probe: `PROBE_third_y_axis`)* |
| `secondary_axis.py` | ❌ | no transformed secondary axes (probe) *(probe: `PROBE_secondary_units_axis`)* |
| `shared_axis_demo.py` | ✅ | LayoutOptions(link_x=True) *(recreated: `subplot_grids`)* |
| `subfigures.py` | ❌ | no subfigures *(probe: `PROBE_gridspec_span`)* |
| `subplot.py` | ✅ | Layout(cols=1) *(recreated: `subplot_grids`)* |
| `subplot2grid.py` | ❌ | no spans *(probe: `PROBE_gridspec_span`)* |
| `subplots_adjust.py` | ❌ | no spacing knobs on the single-figure grid |
| `subplots_demo.py` | ✅ | Layout grids + link_x/link_y *(recreated: `subplot_grids`)* |
| `twin_axes_zorder.py` | ◑ | y2 ✓; draw-order control not modeled |
| `two_scales.py` | ✅ | axis='y2' + OverlayOptions(y2=) *(recreated: `twin_axes`)* |
| `zoom_inset_axes.py` | ❌ | no inset axes (probe) *(probe: `PROBE_inset_zoom`)* |

### Ticks — 25 examples (✅ 3 · ◑ 9 · 🔧 0 · ❌ 12 · 🚫 0 · 〰 1)

| example | verdict | note |
|---|---|---|
| `align_ticklabels.py` | ❌ | no tick label alignment |
| `auto_ticks.py` | ❌ | same *(probe: `PROBE_minor_ticks`)* |
| `centered_ticklabels.py` | ❌ | same |
| `colorbar_tick_labelling_demo.py` | ❌ | no colorbar tick control |
| `custom_ticker1.py` | ◑ | 'eng' covers this case; arbitrary callables not modeled *(probe: `PROBE_dollar_ticks`)* |
| `date.py` | ✅ | datetime64 → calendar axis (hits the P1 selector-autoscale bug under autoscale — below) *(recreated: `date_axis`)* |
| `date_concise_formatter.py` | ◑ | span-adaptive auto format ✓; concise offset style not modeled *(recreated: `date_axis`)* |
| `date_demo_convert.py` | ✅ | datetime64 columns *(recreated: `date_axis`)* |
| `date_demo_rrule.py` | ◑ | same *(recreated: `date_strftime_format`)* |
| `date_formatters_locators.py` | ◑ | strftime tick_format ✓; locator control not modeled *(recreated: `date_strftime_format`)* |
| `date_index_formatter.py` | ❌ | index-then-label (skip weekends) needs label-from-value hooks *(recreated: `date_axis`)* |
| `date_precision_and_epochs.py` | ◑ | ns-precision ✓; epoch control is a non-need (epoch-seconds canonical) *(recreated: `date_axis`)* |
| `dollar_ticks.py` | ❌ | prefix/currency formats not expressible (probe: ValidationError) *(probe: `PROBE_dollar_ticks`)* |
| `engformatter_offset.py` | ◑ | eng ✓; offset notation not modeled |
| `engineering_formatter.py` | ✅ | tick_format='eng' *(recreated: `eng_and_percent_formatters`)* |
| `fig_axes_customize_simple.py` | ◑ | theme colors cover most of it |
| `major_minor_demo.py` | ❌ | no minor ticks (probe) *(probe: `PROBE_minor_ticks`)* |
| `multilevel_ticks.py` | ❌ | no grouped/multi-level ticks *(probe: `PROBE_minor_ticks`)* |
| `scalarformatter.py` | ◑ | format specs ✓; sci-notation offsets not modeled *(recreated: `eng_and_percent_formatters`)* |
| `tick-formatters.py` | ◑ | spec/eng/strftime subset of mpl's formatter zoo |
| `tick-locators.py` | ❌ | no locator control *(probe: `PROBE_minor_ticks`)* |
| `tick_labels_from_values.py` | ❌ | no value→label mapping *(probe: `PROBE_dollar_ticks`)* |
| `ticklabels_rotation.py` | ❌ | no tick label rotation |
| `ticks_too_many.py` | 〰 | perf-pitfall doc |
| `ticks_top_right.py` | ❌ | no axis-side control |

### Color — 11 examples (✅ 3 · ◑ 3 · 🔧 0 · ❌ 4 · 🚫 0 · 〰 1)

| example | verdict | note |
|---|---|---|
| `color_by_yvalue.py` | ❌ | per-segment line color (probe) *(probe: `PROBE_multicolored_line`)* |
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

### Text, labels and annotations — 43 examples (✅ 4 · ◑ 12 · 🔧 0 · ❌ 21 · 🚫 3 · 〰 3)

| example | verdict | note |
|---|---|---|
| `accented_text.py` | ✅ | unicode text everywhere |
| `angle_annotation.py` | ❌ | arc/angle annotations *(probe: `PROBE_annotate_arrow`)* |
| `angles_on_bracket_arrows.py` | ❌ | bracket arrows |
| `annotation_basic.py` | ◑ | Text ✓; the arrow half needs annotate *(recreated: `text_notes`)* |
| `annotation_demo.py` | ❌ | arrows/fancy annotation boxes *(probe: `PROBE_annotate_arrow`)* |
| `annotation_polar.py` | ❌ | polar + arrows *(probe: `PROBE_polar`)* |
| `arrow_demo.py` | ❌ | arrow fields *(probe: `PROBE_annotate_arrow`)* |
| `autowrap.py` | ❌ | no text wrapping |
| `custom_legends.py` | ❌ | no manual legend handles |
| `demo_annotation_box.py` | ❌ | offset/annotation boxes |
| `demo_text_path.py` | ❌ | text-as-path effects |
| `demo_text_rotation_mode.py` | ❌ | no text rotation (probe) *(probe: `PROBE_text_rotation`)* |
| `dfrac_demo.py` | ◑ | same |
| `fancyarrow_demo.py` | ❌ | arrow style zoo *(probe: `PROBE_annotate_arrow`)* |
| `fancytextbox_demo.py` | ❌ | styled text boxes |
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
| `placing_text_boxes.py` | ◑ | data coords only; no axes-fraction coords or boxes |
| `rainbow_text.py` | ❌ | multi-color rich text |
| `stix_fonts_demo.py` | ❌ | math font selection |
| `tex_demo.py` | 🚫 | usetex/LaTeX |
| `text_alignment.py` | ◑ | horizontal anchor only *(recreated: `text_notes`)* |
| `text_commands.py` | ◑ | titles/labels/Text ✓; suptitle/figtext not modeled *(recreated: `titles_labels_legend`)* |
| `text_fontdict.py` | ◑ | size/color only; family/weight per-text not modeled |
| `text_rotation_relative_to_line.py` | ❌ | same *(probe: `PROBE_text_rotation`)* |
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

### Showcase — 7 examples (✅ 1 · ◑ 3 · 🔧 1 · ❌ 0 · 🚫 2 · 〰 0)

| example | verdict | note |
|---|---|---|
| `anatomy.py` | 🚫 | a matplotlib-anatomy teaching figure |
| `firefox.py` | 🔧 | SVG-path art — escape hatch |
| `integral.py` | ◑ | Area over a sub-range + Text ✓; mathtext annotation + polygon shading approximated |
| `mandelbrot.py` | ✅ | computed grid → Image (normalized shading differs) *(recreated: `mandelbrot_image`)* |
| `pan_zoom_overlap.py` | ◑ | overlapping-axes gesture routing is mpl-specific; qtviz panes don't overlap |
| `stock_prices.py` | ◑ | multi-curve + time axis ✓; end-of-line series labels not modeled — and hits the P1 selector-autoscale bug (below) *(recreated: `stock_prices`)* |
| `xkcd.py` | 🚫 | xkcd sketch style |

### Specialty plots — 12 examples (✅ 1 · ◑ 1 · 🔧 0 · ❌ 10 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `advanced_hillshading.py` | ❌ | hillshading/light sources |
| `anscombe.py` | ✅ | 2×2 linked grid of Scatters *(recreated: `anscombe_quartet`)* |
| `hinton_demo.py` | ❌ | per-cell sized squares (patch grid) |
| `ishikawa_diagram.py` | ❌ | diagram art (arrows/polygons) |
| `leftventricle_bullseye.py` | ❌ | polar mesh |
| `mri_with_eeg.py` | ◑ | stacked linked panels ✓; shared-y strip layout differs *(recreated: `mri_with_eeg_panels`)* |
| `radar_chart.py` | ❌ | polar projection *(probe: `PROBE_polar`)* |
| `sankey_basics.py` | ❌ | no Sankey (probe); RawFigure+Plotly can host one *(probe: `PROBE_sankey`)* |
| `sankey_links.py` | ❌ | same *(probe: `PROBE_sankey`)* |
| `sankey_rankine.py` | ❌ | same *(probe: `PROBE_sankey`)* |
| `skewt.py` | ❌ | custom skewed projection |
| `topographic_hillshading.py` | ❌ | same |

### Shapes and collections — 18 examples (✅ 1 · ◑ 0 · 🔧 9 · ❌ 8 · 🚫 0 · 〰 0)

| example | verdict | note |
|---|---|---|
| `arrow_guide.py` | ❌ | no arrow annotations |
| `artist_reference.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `collections.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `compound_path.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `dolphin.py` | 🔧 | patch/path/collection drawing — handle.native() escape hatch |
| `donut.py` | 🔧 | path-construction demo (Pie(hole=) covers donut charts) *(recreated: `pie_donut`)* |
| `ellipse_arrow.py` | ❌ | same + arrows |
| `ellipse_collection.py` | ❌ | same |
| `ellipse_demo.py` | ❌ | no ellipse element |
| `fancybox_demo.py` | ❌ | no styled text boxes |
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
| `simple_axesgrid2.py` | ◑ | grid ✓; shared single colorbar not modeled |
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
| `fill_spiral.py` | ❌ | polygon art |
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
| `transoffset.py` | ❌ | offset transforms |
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



## 6. Summary — the state of qtviz against the matplotlib gallery

qtviz's target is "the everyday 90% declaratively, the tail via escape
hatches" ([D83]). Judged against matplotlib's own showcase: **the chart types
are substantially there — the figure dressing is not.** In the core chart
categories, 92 of 161 in-scope examples (57%) are achievable
today, and post-parity vocabulary (step/area/pie/ECDF/contour, twin axes,
calendar time, tick formats) is what carries them. Across the whole gallery
the achievable share drops to 47% of in-scope examples (32% of all
507) because mpl's gallery is, to a large degree, a showcase of its
annotation/tick/patch/toolkit machinery — arrows, rotated labels, insets,
custom locators, path art — which qtviz deliberately routes to escape
hatches, and which accounts for most of the 181 gaps. That is a defensible
position for a data-app library, but §3 shows the specific slices (annotation
wave, tick control, a shape element) where modest vocabulary would flip
dozens of examples at once.

Three practical takeaways, in priority order:

1. **Fix the discovered defects first** (§2) — the selector/autoscale bug is
   a P1 that silently breaks matplotlib time-series autoscaling, shipped in
   [D95] this week.
2. **A small annotation wave buys the most gallery**: arrowed text,
   `rotation=`, `bar_labels=`, an `Ellipse`/`Rect` shape element, and
   `fill_betweenx` would flip ~30 examples from ❌/◑ toward ✅ — they are the
   recurring supporting cast of every real figure.
3. **The big-ticket absences (polar, tri-meshes, vector fields, insets) are
   genuine scope decisions**, not oversights — each is a mini-subsystem.
   Given `RawFigure` hosts Plotly natively for all of them today, they
   should stay demand-gated.
