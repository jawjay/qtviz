# Gallery

Every example is a self-contained, runnable script in the repo's
[`examples/`](https://github.com/markjajeh/qtviz/tree/main/examples) directory. Each
exposes a `build()` (returns the widget, handy for embedding/testing) and a `main()`
(shows a window):

```bash
uv run python examples/01_hello.py
```

## Real-world scenarios

Larger examples that combine several features around a realistic dataset and data type.

| Example | Shows |
|---------|-------|
| `26_telemetry_monitoring` | Sensor time series: a rolling baseline, a 3σ tolerance `Spread`, flagged-anomaly `Scatter`, and an X-linked residual panel derived with an `Expression`. |
| `27_market_analytics` | Equity price `Curve` + 20/50-day moving averages + a Bollinger `Spread`, over an X-linked volume `Bars` panel; brush a window of days. |
| `28_event_density_map` | 2M categorized events → a Datashaded categorical density map; hover anywhere for the event count under the cursor (stays correct as you zoom). |
| `29_climate_field` | An `xarray` 2-D field rendered as an `Image` map plus a 1-D `da.isel` cross-section `Curve` — one library, two data shapes, X-linked. |

## Native

| Example | Shows |
|---------|-------|
| `01_hello` | The smallest program — a scatter in a `View`. |
| `02_composition` | Overlay with `*`, lay out with `+`. |
| `03_backends` | The same plot via pyqtgraph / matplotlib; switch at runtime. |
| `04_theming` | Light/dark themes, colors, custom palette. |
| `05_interaction` | Typed events — brush-select, pick, range. |
| `06_data_binding` | Column names, `Expression`s, callables, arrays. |
| `07_mixed_backends` | A pyqtgraph pane beside a matplotlib pane, one event stream. |
| `08_gallery` | All eight element types in a grid. |
| `09_datashader` | Millions of points → a density raster, re-aggregated on zoom. |
| `10_out_of_core` | A lazy Dask DataFrame datashaded out-of-core. |
| `11_datashader_matplotlib` | The same datashaded scatter on matplotlib. |
| `12_color_mapping` | `color_by` / `size_by` → per-point color/size + automatic legend. |
| `25_raster_inspect` | Hover a datashaded plot for the `count` under the cursor. |
| `dashboard_native` | 3-panel linked dashboard (shared X, brushing, dark theme). |

## Reactive & adapter

| Example | Shows |
|---------|-------|
| `21_reactive_crossfilter` | Brush one view → a `Signal` re-renders another. |
| `22_from_holoviews` | Render a HoloViews `scatter * curve + bars` tree natively. |
| `23_from_holoviews_dynamicmap` | Drive a HoloViews `DynamicMap` with a Qt control. |
| `24_from_hvplot` | A pandas `df.hvplot(kind="scatter")` one-liner as a native widget. |

## webengine

| Example | Shows |
|---------|-------|
| `13_webengine` | A `Scatter` through Plotly in a `QWebEngineView`; events bridge back. |
| `14_webengine_overlay` | An `Overlay` → multiple Plotly traces; pick carries the series id. |
| `15_webengine_elements` | Spread + Curve + Scatter in one Plotly figure. |
| `16_webengine_export` | Export a webengine plot to PNG. |
| `17_webengine_heatmap` | A tabular `Heatmap` → a Plotly heatmap. |
| `18_webengine_raw_figure` | `RawFigure` — host a Plotly 3-D surface qtviz doesn't model. |
| `19_webengine_holoviews` | `RawFigure` + HoloViews via Bokeh, events bridged back. |
| `20_mixed_native_web` | A native pane beside a webengine pane, one event stream. |

The full index with per-example notes lives in
[`examples/README.md`](https://github.com/markjajeh/qtviz/blob/main/examples/README.md).
