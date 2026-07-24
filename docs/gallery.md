# Gallery

Every example is a self-contained, runnable script in the repo's
[`examples/`](https://github.com/jawjay/qtviz/tree/main/examples) directory. Each
exposes a `build()` (returns the widget, handy for embedding/testing) and a `main()`
(shows a window):

```bash
uv run python examples/01_hello.py
```

The screenshots below are captured straight from these scripts
(`uv run python tools/capture_screenshots.py` regenerates them).

## Real-world scenarios

Larger examples that combine several features around a realistic dataset and data type.

### `26_telemetry_monitoring` — sensor monitoring

Sensor time series: a rolling baseline, a 3σ tolerance `Spread`, flagged-anomaly
`Scatter`, and an X-linked residual panel derived with an `Expression`.

![Telemetry monitoring dashboard](images/examples/26_telemetry_monitoring.png)

### `27_market_analytics` — market analytics

Equity price `Curve` + 20/50-day moving averages + a Bollinger `Spread`, over an
X-linked volume `Bars` panel; brush a window of days.

![Market analytics dashboard](images/examples/27_market_analytics.png)

### `28_event_density_map` — big-data density map

2M categorized events → a Datashaded categorical density map; hover anywhere for
the event count under the cursor (stays correct as you zoom).

![Categorical event density map](images/examples/28_event_density_map.png)

### `29_climate_field` — gridded science

An `xarray` 2-D field rendered as an `Image` map plus a 1-D `da.isel`
cross-section `Curve` — one library, two data shapes, X-linked.

![Climate field map and cross-section](images/examples/29_climate_field.png)

### `30_xarray_sensor_lines` — xarray cube

A 3-D `xarray` cube `10_000 × 4 × 250` `(time, sensor, instance)`: `.sel` one
sensor, then overlay all 250 instances (~2.5M line points) as faint `Curve`s with
a bold `.mean` envelope.

![250 overlaid instance lines with a mean envelope](images/examples/30_xarray_sensor_lines.png)

### `34_streaming_telemetry` — live + history + detail

A live rolling feed (`qv.stream`), the accumulated 400k-point history datashaded,
and a brush-driven detail panel wired through a `Signal`.

![Streaming telemetry with datashaded history](images/examples/34_streaming_telemetry.png)

### `dashboard_native` — linked dashboard

3-panel linked dashboard (shared X, brushing, dark theme) in under sixty lines.

![Three-panel linked dashboard](images/examples/dashboard_native.png)

## Native

### `01_hello` — the smallest program

A scatter in a `View` — six lines.

![Hello-world scatter](images/examples/01_hello.png)

### `02_composition` — Overlay and Layout

Overlay with `*`, lay out with `+`.

![Overlay beside a histogram panel](images/examples/02_composition.png)

### `03_backends` — switch engines at runtime

The same plot via pyqtgraph / matplotlib; switch at runtime.

![Backend switching demo](images/examples/03_backends.png)

### `04_theming` — themes and palettes

Light/dark themes, colors, and a registered custom palette.

![Three curves from a custom palette on the dark theme](images/examples/04_theming.png)

### `05_interaction` — typed events

Typed events — brush-select, pick, range.

![Interaction demo](images/examples/05_interaction.png)

### `06_data_binding` — accessors

Bind channels to column names, **Expressions**, callables, arrays.

![Curves derived via expressions and callables](images/examples/06_data_binding.png)

### `07_mixed_backends` — two engines, one window

A pyqtgraph pane beside a matplotlib pane, one event stream.

![pyqtgraph beside matplotlib](images/examples/07_mixed_backends.png)

### `08_gallery` — the element vocabulary

All eight core element types in a grid.

![Eight element types in a grid](images/examples/08_gallery.png)

### `09_datashader` — millions of points

Millions of points → a density raster that re-aggregates to the viewport on zoom.

![Datashaded density raster](images/examples/09_datashader.png)

### `10_out_of_core` — lazy Dask

A lazy Dask DataFrame datashaded out-of-core — never fully materialized.

![Out-of-core datashaded scatter](images/examples/10_out_of_core.png)

### `11_datashader_matplotlib` — backend-agnostic rasters

The same datashaded scatter on matplotlib — zoom still re-aggregates.

![Datashaded scatter on the matplotlib backend](images/examples/11_datashader_matplotlib.png)

### `12_color_mapping` — color & size encoding

`color_by` / `size_by` a column → per-point color/size + an automatic legend /
colorbar.

![Categorical legend and continuous colorbar](images/examples/12_color_mapping.png)

### `25_raster_inspect` — hover a raster

Hover a 1M-point datashaded scatter; `HoverEvent.value` reports the `count`
under the cursor.

![Raster hover-inspect](images/examples/25_raster_inspect.png)

### `31_axis_labels` — axis labels & titles

`OverlayOptions(title, x_label, y_label)` on each surface; per-pane labels in a
`Layout`; renders identically on every backend.

![Titled panes with axis labels](images/examples/31_axis_labels.png)

### `32_datashader_legends` — datashader legends & aggregation

A themed category-blend raster with a legend beside an `agg="max"` raster with a
colorbar; colors come from the `Theme`.

![Datashader legend and colorbar](images/examples/32_datashader_legends.png)

### `33_native_escape_hatch` — the live pyqtgraph item

`view.native(element.id)` returns the live pyqtgraph `ScatterPlotItem`; wire a
native crosshair the typed events don't model.

![Native escape hatch with crosshair](images/examples/33_native_escape_hatch.png)

## Reactive & adapter

### `21_reactive_crossfilter` — linked brushing

Brush one view → a `Signal` + `derived` re-renders another with the selected rows.

![Reactive crossfilter](images/examples/21_reactive_crossfilter.png)

### `22_from_holoviews` — HoloViews, natively

Render a HoloViews `scatter * curve + bars` tree as native qtviz Elements — no
browser.

![HoloViews tree rendered natively](images/examples/22_from_holoviews.png)

### `23_from_holoviews_dynamicmap` — DynamicMap

Drive a HoloViews `DynamicMap` kdim with a Qt slider; `from_holoviews_dmap` →
`Signal[Node]` re-renders.

![DynamicMap driven by a Qt slider](images/examples/23_from_holoviews_dynamicmap.png)

### `24_from_hvplot` — hvplot one-liner

A pandas `df.hvplot(kind="scatter")` one-liner rendered as a native Qt widget.

![hvplot scatter as a native widget](images/examples/24_from_hvplot.png)

## webengine

These need the `webengine` extra and a real display.

### `13_webengine` — Plotly in a Qt window

A `Scatter` through Plotly in a `QWebEngineView`; typed events bridge back; the
button swaps the same Element to a native backend.

![Plotly scatter in a QWebEngineView](images/examples/13_webengine.png)

### `14_webengine_overlay` — multi-trace figures

An `Overlay` → multiple Plotly traces; a `PickEvent` carries the originating
series id.

![Overlay as multiple Plotly traces](images/examples/14_webengine_overlay.png)

### `15_webengine_elements` — mixed elements, one figure

Spread + Curve + Scatter in one webengine Plotly figure.

![Spread, curve, and scatter in one Plotly figure](images/examples/15_webengine_elements.png)

### `16_webengine_export` — PNG export

Export a webengine plot to PNG (`view.handle.export("png", path)`).

![Webengine PNG export](images/examples/16_webengine_export.png)

### `17_webengine_heatmap` — Plotly heatmap

A tabular `Heatmap` (x/y/z) → a Plotly heatmap with a Viridis colorscale.

![Plotly heatmap with hover tooltip](images/examples/17_webengine_heatmap.png)

### `18_webengine_raw_figure` — RawFigure passthrough

Host an existing Plotly figure (a 3-D surface) qtviz doesn't natively model;
events still bridge back.

![Plotly 3-D surface hosted via RawFigure](images/examples/18_webengine_raw_figure.png)

### `19_webengine_holoviews` — HoloViews via Bokeh

`RawFigure` + HoloViews rendered via Bokeh, with tap / box-select / range
arriving as qtviz typed events.

![HoloViews figure via Bokeh in a Qt window](images/examples/19_webengine_holoviews.png)

### `20_mixed_native_web` — native beside web

A native pyqtgraph pane beside a webengine Plotly pane in one window, sharing one
event stream.

![Native pane beside a webengine pane](images/examples/20_mixed_native_web.png)

---

The full index with per-example notes and required extras lives in
[`examples/README.md`](https://github.com/jawjay/qtviz/blob/main/examples/README.md).
