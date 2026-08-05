# qtviz examples

Runnable, self-contained scripts. Each exposes a `build()` that returns the
widget (handy for embedding/testing) and a `main()` that shows a window. The
preview images live in [`docs/images/examples/`](../docs/images/examples) and are
captured from these scripts by `uv run python tools/capture_screenshots.py`.

```bash
uv run python examples/01_hello.py
```

Most need the matplotlib extra for the backend-switching / mixed-backend demos:

```bash
uv sync --extra matplotlib --extra dev
```

| # | File | Shows | Preview |
|---|------|-------|---------|
| 1 | [`01_hello.py`](01_hello.py) | The smallest program — a scatter in a `View`. | <a href="../docs/images/examples/01_hello.png"><img src="../docs/images/examples/01_hello.png" width="260" alt="01_hello"></a> |
| 2 | [`02_composition.py`](02_composition.py) | Overlay with `*`, lay out with `+`. | <a href="../docs/images/examples/02_composition.png"><img src="../docs/images/examples/02_composition.png" width="260" alt="02_composition"></a> |
| 3 | [`03_backends.py`](03_backends.py) | The same plot via pyqtgraph / matplotlib; switch at runtime. | <a href="../docs/images/examples/03_backends.png"><img src="../docs/images/examples/03_backends.png" width="260" alt="03_backends"></a> |
| 4 | [`04_theming.py`](04_theming.py) | Light/dark themes, colors, custom palette. | <a href="../docs/images/examples/04_theming.png"><img src="../docs/images/examples/04_theming.png" width="260" alt="04_theming"></a> |
| 5 | [`05_interaction.py`](05_interaction.py) | Typed events — brush-select, pick, range. | <a href="../docs/images/examples/05_interaction.png"><img src="../docs/images/examples/05_interaction.png" width="260" alt="05_interaction"></a> |
| 6 | [`06_data_binding.py`](06_data_binding.py) | Bind channels to names, **Expressions**, callables, arrays. | <a href="../docs/images/examples/06_data_binding.png"><img src="../docs/images/examples/06_data_binding.png" width="260" alt="06_data_binding"></a> |
| 7 | [`07_mixed_backends.py`](07_mixed_backends.py) | A pyqtgraph pane beside a matplotlib pane, one event stream. | <a href="../docs/images/examples/07_mixed_backends.png"><img src="../docs/images/examples/07_mixed_backends.png" width="260" alt="07_mixed_backends"></a> |
| 8 | [`08_gallery.py`](08_gallery.py) | The core element vocabulary in one grid. | <a href="../docs/images/examples/08_gallery.png"><img src="../docs/images/examples/08_gallery.png" width="260" alt="08_gallery"></a> |
| 9 | [`09_datashader.py`](09_datashader.py) | Millions of points → a density raster that **re-aggregates to the viewport on zoom**. | <a href="../docs/images/examples/09_datashader.png"><img src="../docs/images/examples/09_datashader.png" width="260" alt="09_datashader"></a> |
| 10 | [`10_out_of_core.py`](10_out_of_core.py) | A lazy **Dask** DataFrame datashaded out-of-core — never fully materialized. | <a href="../docs/images/examples/10_out_of_core.png"><img src="../docs/images/examples/10_out_of_core.png" width="260" alt="10_out_of_core"></a> |
| 11 | [`11_datashader_matplotlib.py`](11_datashader_matplotlib.py) | The same datashaded scatter on **matplotlib** — backend-agnostic, zoom re-aggregates. | <a href="../docs/images/examples/11_datashader_matplotlib.png"><img src="../docs/images/examples/11_datashader_matplotlib.png" width="260" alt="11_datashader_matplotlib"></a> |
| 12 | [`12_color_mapping.py`](12_color_mapping.py) | `color_by` / `size_by` a column → per-point color/size + an **automatic legend / colorbar**. | <a href="../docs/images/examples/12_color_mapping.png"><img src="../docs/images/examples/12_color_mapping.png" width="260" alt="12_color_mapping"></a> |
| 13 | [`13_webengine.py`](13_webengine.py) | The same `Scatter` rendered through **Plotly in a QWebEngineView** (`backend="webengine"`); typed events bridge back; toggle to a native backend. | <a href="../docs/images/examples/13_webengine.png"><img src="../docs/images/examples/13_webengine.png" width="260" alt="13_webengine"></a> |
| 14 | [`14_webengine_overlay.py`](14_webengine_overlay.py) | An `Overlay` → multiple Plotly traces in one figure; a PickEvent carries the originating **series id**. | <a href="../docs/images/examples/14_webengine_overlay.png"><img src="../docs/images/examples/14_webengine_overlay.png" width="260" alt="14_webengine_overlay"></a> |
| 15 | [`15_webengine_elements.py`](15_webengine_elements.py) | Several element types (Spread + Curve + Scatter) in **one** webengine Plotly figure. | <a href="../docs/images/examples/15_webengine_elements.png"><img src="../docs/images/examples/15_webengine_elements.png" width="260" alt="15_webengine_elements"></a> |
| 16 | [`16_webengine_export.py`](16_webengine_export.py) | Export a webengine plot to **PNG** (`handle.export("png", path)`). | <a href="../docs/images/examples/16_webengine_export.png"><img src="../docs/images/examples/16_webengine_export.png" width="260" alt="16_webengine_export"></a> |
| 17 | [`17_webengine_heatmap.py`](17_webengine_heatmap.py) | A tabular `Heatmap` (x/y/z) → a Plotly heatmap with a Viridis colorscale. | <a href="../docs/images/examples/17_webengine_heatmap.png"><img src="../docs/images/examples/17_webengine_heatmap.png" width="260" alt="17_webengine_heatmap"></a> |
| 18 | [`18_webengine_raw_figure.py`](18_webengine_raw_figure.py) | **`RawFigure`** — host an existing Plotly figure (a 3-D surface) qtviz doesn't natively model; events still bridge back. | <a href="../docs/images/examples/18_webengine_raw_figure.png"><img src="../docs/images/examples/18_webengine_raw_figure.png" width="260" alt="18_webengine_raw_figure"></a> |
| 19 | [`19_webengine_holoviews.py`](19_webengine_holoviews.py) | **`RawFigure` + HoloViews** — a HoloViews figure rendered via Bokeh, with tap / box-select / range arriving as qtviz typed events. | <a href="../docs/images/examples/19_webengine_holoviews.png"><img src="../docs/images/examples/19_webengine_holoviews.png" width="260" alt="19_webengine_holoviews"></a> |
| 20 | [`20_mixed_native_web.py`](20_mixed_native_web.py) | **Mixed backends** — a native pyqtgraph pane beside a webengine Plotly pane in one window, sharing one event stream. | <a href="../docs/images/examples/20_mixed_native_web.png"><img src="../docs/images/examples/20_mixed_native_web.png" width="260" alt="20_mixed_native_web"></a> |
| 21 | [`21_reactive_crossfilter.py`](21_reactive_crossfilter.py) | **Reactive crossfilter** — brush one view, a `Signal` + `derived` re-renders another with the selected rows (spec §9). Native, offline. | <a href="../docs/images/examples/21_reactive_crossfilter.png"><img src="../docs/images/examples/21_reactive_crossfilter.png" width="260" alt="21_reactive_crossfilter"></a> |
| 22 | [`22_from_holoviews.py`](22_from_holoviews.py) | **`from_holoviews`** — translate a HoloViews `scatter * curve + bars` tree into native qtviz Elements; no browser. | <a href="../docs/images/examples/22_from_holoviews.png"><img src="../docs/images/examples/22_from_holoviews.png" width="260" alt="22_from_holoviews"></a> |
| 23 | [`23_from_holoviews_dynamicmap.py`](23_from_holoviews_dynamicmap.py) | **HoloViews `DynamicMap`** — drive a `freq` kdim with a Qt control; `from_holoviews_dmap` → `Signal[Node]` re-renders ([D44] L1). | <a href="../docs/images/examples/23_from_holoviews_dynamicmap.png"><img src="../docs/images/examples/23_from_holoviews_dynamicmap.png" width="260" alt="23_from_holoviews_dynamicmap"></a> |
| 24 | [`24_from_hvplot.py`](24_from_hvplot.py) | **`from_hvplot`** — a pandas `df.hvplot(kind="scatter")` one-liner rendered as a native Qt widget ([D43]). | <a href="../docs/images/examples/24_from_hvplot.png"><img src="../docs/images/examples/24_from_hvplot.png" width="260" alt="24_from_hvplot"></a> |
| 25 | [`25_raster_inspect.py`](25_raster_inspect.py) | **Raster hover-inspect** — hover a 1M-point datashaded scatter; `HoverEvent.value` reports the `count` under the cursor ([D46]). | <a href="../docs/images/examples/25_raster_inspect.png"><img src="../docs/images/examples/25_raster_inspect.png" width="260" alt="25_raster_inspect"></a> |
| 26 | [`26_telemetry_monitoring.py`](26_telemetry_monitoring.py) | **Real-world: sensor monitoring** — rolling baseline + 3σ `Spread` band + flagged-anomaly `Scatter`; an X-linked residual panel derived via an `Expression`. | <a href="../docs/images/examples/26_telemetry_monitoring.png"><img src="../docs/images/examples/26_telemetry_monitoring.png" width="260" alt="26_telemetry_monitoring"></a> |
| 27 | [`27_market_analytics.py`](27_market_analytics.py) | **Real-world: market analytics** — price `Curve` + 20/50-day MAs + Bollinger `Spread`, over an X-linked volume `Bars` panel; brush a day window. | <a href="../docs/images/examples/27_market_analytics.png"><img src="../docs/images/examples/27_market_analytics.png" width="260" alt="27_market_analytics"></a> |
| 28 | [`28_event_density_map.py`](28_event_density_map.py) | **Real-world: big-data map** — 2M categorized events → Datashaded categorical density; hover for the event count under the cursor. | <a href="../docs/images/examples/28_event_density_map.png"><img src="../docs/images/examples/28_event_density_map.png" width="260" alt="28_event_density_map"></a> |
| 29 | [`29_climate_field.py`](29_climate_field.py) | **Real-world: gridded science** — an `xarray` 2-D field → `Image` map + a 1-D `da.isel` cross-section `Curve`, X-linked. | <a href="../docs/images/examples/29_climate_field.png"><img src="../docs/images/examples/29_climate_field.png" width="260" alt="29_climate_field"></a> |
| 30 | [`30_xarray_sensor_lines.py`](30_xarray_sensor_lines.py) | **Real-world: xarray cube** — a 3-D `10_000 × 4 × 250` `(time, sensor, instance)` `DataArray`; `.sel` one sensor, overlay all 250 instances (~2.5M line points) as faint `Curve`s + a bold `.mean` envelope. | <a href="../docs/images/examples/30_xarray_sensor_lines.png"><img src="../docs/images/examples/30_xarray_sensor_lines.png" width="260" alt="30_xarray_sensor_lines"></a> |
| 31 | [`31_axis_labels.py`](31_axis_labels.py) | **Axis labels & titles** — `.opts(title=…, x=…, y=…)` on each surface ([D133]); per-pane labels in a `Layout`; renders identically on every backend. | <a href="../docs/images/examples/31_axis_labels.png"><img src="../docs/images/examples/31_axis_labels.png" width="260" alt="31_axis_labels"></a> |
| 32 | [`32_datashader_legends.py`](32_datashader_legends.py) | **Datashader legends & aggregation** — themed category-blend raster **with a legend** beside a `agg="max"` raster **with a colorbar**; colors come from the `Theme`, the colorbar tracks the viewport ([D47]–[D50]). | <a href="../docs/images/examples/32_datashader_legends.png"><img src="../docs/images/examples/32_datashader_legends.png" width="260" alt="32_datashader_legends"></a> |
| 33 | [`33_native_escape_hatch.py`](33_native_escape_hatch.py) | **Native escape hatch** — `view.native(element.id)` returns the live pyqtgraph `ScatterPlotItem`; wire a native crosshair (`InfiniteLine` + `sigMouseMoved`) the typed events don't model. Non-portable by design; the live object never touches the immutable Element ([D53]). | <a href="../docs/images/examples/33_native_escape_hatch.png"><img src="../docs/images/examples/33_native_escape_hatch.png" width="260" alt="33_native_escape_hatch"></a> |
| 34 | [`34_streaming_telemetry.py`](34_streaming_telemetry.py) | **Streaming telemetry** — a live `qv.stream` feed (rolling 2k window) beside the datashaded 400k-point history; brush the raster → a `Signal` re-renders the detail panel. | <a href="../docs/images/examples/34_streaming_telemetry.png"><img src="../docs/images/examples/34_streaming_telemetry.png" width="260" alt="34_streaming_telemetry"></a> |
| 35 | [`35_everyday_figures.py`](35_everyday_figures.py) | **The everyday figures** — the parity-program vocabulary in one grid: step curve + markers, stacked `Area`, horizontal grouped `Bars`, `Pie` donut, `Ecdf` with percent ticks, filled `Contour`, SI tick formatting + grid toggle, a dual-axis pair, a `Quiver` field with a reference key, a boundary-level `Mesh`, a `Stem` series, and an annotated `Heatmap` — with the native toolbar (`View(toolbar=True)`). | <a href="../docs/images/examples/35_everyday_figures.png"><img src="../docs/images/examples/35_everyday_figures.png" width="260" alt="35_everyday_figures"></a> |
| 36 | [`36_mosaic_layout.py`](36_mosaic_layout.py) | **Mosaic layout** — `Layout.mosaic("AAB\nCCB", …)`: spanning panes from an ASCII plan, `width_ratios` track sizing, and a figure-level suptitle ([D108]). | <a href="../docs/images/examples/36_mosaic_layout.png"><img src="../docs/images/examples/36_mosaic_layout.png" width="260" alt="36_mosaic_layout"></a> |
| — | [`dashboard_native.py`](dashboard_native.py) | 3-panel linked dashboard (shared X, brushing, dark theme). | <a href="../docs/images/examples/dashboard_native.png"><img src="../docs/images/examples/dashboard_native.png" width="260" alt="dashboard_native"></a> |

Examples 9–11 need the datashader extra (10 also needs dask; 11 also matplotlib):

```bash
uv sync --extra datashader --extra dask --extra matplotlib --extra dev
```

Examples 22–24 use the HoloViews adapter; 24 also needs the `hvplot` extra:

```bash
uv sync --extra holoviews --extra hvplot --extra dev
```

Examples 25, 32, and 34 need the `datashader` extra.

Examples 26–30 are larger "real-world" scenarios. 26 and 27 use pandas (already present
via the data extras); 28 needs `datashader`; 29 and 30 need `xarray`:

```bash
uv sync --extra datashader --extra xarray --extra dev
```

Examples 13–20 use the **`webengine` backend** (qtviz Elements → Plotly in a Qt
WebEngine view, plus `RawFigure` passthrough for Plotly/Bokeh/HoloViews, and a
mixed native+webengine layout). They need the webengine extra and a real
display (a `QWebEngineView` segfaults at teardown under offscreen Qt):

```bash
uv sync --extra webengine --extra dev
```
