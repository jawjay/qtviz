# qtviz examples

Runnable, self-contained scripts. Each exposes a `build()` that returns the
widget (handy for embedding/testing) and a `main()` that shows a window.

```bash
uv run python examples/01_hello.py
```

Most need the matplotlib extra for the backend-switching / mixed-backend demos:

```bash
uv sync --extra matplotlib --extra dev
```

| # | File | Shows |
|---|------|-------|
| 1 | [`01_hello.py`](01_hello.py) | The smallest program — a scatter in a `View`. |
| 2 | [`02_composition.py`](02_composition.py) | Overlay with `*`, lay out with `+`. |
| 3 | [`03_backends.py`](03_backends.py) | The same plot via pyqtgraph / matplotlib; switch at runtime. |
| 4 | [`04_theming.py`](04_theming.py) | Light/dark themes, colors, custom palette. |
| 5 | [`05_interaction.py`](05_interaction.py) | Typed events — brush-select, pick, range. |
| 6 | [`06_data_binding.py`](06_data_binding.py) | Bind channels to names, **Expressions**, callables, arrays. |
| 7 | [`07_mixed_backends.py`](07_mixed_backends.py) | A pyqtgraph pane beside a matplotlib pane, one event stream. |
| 8 | [`08_gallery.py`](08_gallery.py) | All eight element types in a grid. |
| 9 | [`09_datashader.py`](09_datashader.py) | Millions of points → a density raster that **re-aggregates to the viewport on zoom**. |
| 10 | [`10_out_of_core.py`](10_out_of_core.py) | A lazy **Dask** DataFrame datashaded out-of-core — never fully materialized. |
| 11 | [`11_datashader_matplotlib.py`](11_datashader_matplotlib.py) | The same datashaded scatter on **matplotlib** — backend-agnostic, zoom re-aggregates. |
| 12 | [`12_color_mapping.py`](12_color_mapping.py) | `color_by` / `size_by` a column → per-point color/size + an **automatic legend / colorbar**. |
| 13 | [`13_webengine.py`](13_webengine.py) | The same `Scatter` rendered through **Plotly in a QWebEngineView** (`backend="webengine"`); typed events bridge back; toggle to a native backend. |
| 14 | [`14_webengine_overlay.py`](14_webengine_overlay.py) | An `Overlay` → multiple Plotly traces in one figure; a PickEvent carries the originating **series id**. |
| 15 | [`15_webengine_elements.py`](15_webengine_elements.py) | Several element types (Spread + Curve + Scatter) in **one** webengine Plotly figure. |
| 16 | [`16_webengine_export.py`](16_webengine_export.py) | Export a webengine plot to **PNG** (`handle.export("png", path)`). |
| 17 | [`17_webengine_heatmap.py`](17_webengine_heatmap.py) | A tabular `Heatmap` (x/y/z) → a Plotly heatmap with a Viridis colorscale. |
| 18 | [`18_webengine_raw_figure.py`](18_webengine_raw_figure.py) | **`RawFigure`** — host an existing Plotly figure (a 3-D surface) qtviz doesn't natively model; events still bridge back. |
| 19 | [`19_webengine_holoviews.py`](19_webengine_holoviews.py) | **`RawFigure` + HoloViews** — a HoloViews figure rendered via Bokeh, with tap / box-select / range arriving as qtviz typed events (W3b). |
| 20 | [`20_mixed_native_web.py`](20_mixed_native_web.py) | **Mixed backends** — a native pyqtgraph pane beside a webengine Plotly pane in one window, sharing one event stream (W4). |
| 21 | [`21_reactive_crossfilter.py`](21_reactive_crossfilter.py) | **Reactive crossfilter** — brush one view, a `Signal` + `derived` re-renders another with the selected rows (spec §9). Native, offline. |
| 22 | [`22_from_holoviews.py`](22_from_holoviews.py) | **`from_holoviews`** — translate a HoloViews `scatter * curve + bars` tree into native qtviz Elements; no browser. |
| 23 | [`23_from_holoviews_dynamicmap.py`](23_from_holoviews_dynamicmap.py) | **HoloViews `DynamicMap`** — drive a `freq` kdim with a Qt control; `from_holoviews_dmap` → `Signal[Node]` re-renders ([D44] L1). |
| 24 | [`24_from_hvplot.py`](24_from_hvplot.py) | **`from_hvplot`** — a pandas `df.hvplot(kind="scatter")` one-liner rendered as a native Qt widget ([D43]). |
| 25 | [`25_raster_inspect.py`](25_raster_inspect.py) | **Raster hover-inspect** — hover a 1M-point datashaded scatter; `HoverEvent.value` reports the `count` under the cursor ([D46]). |
| — | [`dashboard_native.py`](dashboard_native.py) | 3-panel linked dashboard (shared X, brushing, dark theme). |

Examples 9–11 need the datashader extra (10 also needs dask; 11 also matplotlib):

```bash
uv sync --extra datashader --extra dask --extra matplotlib --extra dev
```

Examples 22–24 use the HoloViews adapter; 24 also needs the `hvplot` extra:

```bash
uv sync --extra holoviews --extra hvplot --extra dev
```

Example 25 needs the `datashader` extra.

Examples 13–20 use the **`webengine` backend** (qtviz Elements → Plotly in a Qt
WebEngine view, plus `RawFigure` passthrough for Plotly/Bokeh/HoloViews, and a
mixed native+webengine layout; roadmap Phase 5, W1–W4). They need the webengine
extra and a real display (a `QWebEngineView` segfaults at teardown under offscreen
Qt):

```bash
uv sync --extra webengine --extra dev
```

The [`webengine/`](webengine) folder holds the remaining **legacy** `qtwebplot`
hello-world examples (`hello_plotly` / `hello_bokeh` / `hello_holoviews`), which
drive the bridge directly through the old `PlotView` (reachable via the deprecation
shim) rather than through a qtviz `View`. The legacy multi-pane / linked-plot demos
were removed in W4 — `qv.Layout` (examples 02, 07, 20) supersedes them.
