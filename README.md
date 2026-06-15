# qtviz

**Declarative, native-Qt plotting for data-intensive desktop apps.**

Describe a plot once as immutable data, then render it through whichever engine
fits the moment — **pyqtgraph** (fast, OpenGL, interactive), **matplotlib**
(publication-quality, vector export), or **webengine** (interactive Plotly in an
embedded browser view). The same `Element` draws identically on all three, swaps
backends at runtime, and drops into any PySide6 application as a plain `QWidget`.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Qt](https://img.shields.io/badge/Qt-PySide6-41cd52)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-pre--release-orange)

```python
import numpy as np
from PySide6.QtWidgets import QApplication
import qtviz as qv

app = QApplication([])
x = np.linspace(0, 10, 500)

view = qv.View(qv.Scatter({"x": x, "y": np.sin(x)}, x="x", y="y"))
view.show()
app.exec()
```

That is a complete program: a real Qt window, an OpenGL-accelerated scatter, pan
and zoom out of the box. Change one keyword — `backend="matplotlib"` or
`backend="webengine"` — and the same line renders through a different engine.

> **Status — `0.1`, pre-release.** The native stack (data model, pyqtgraph +
> matplotlib backends, interaction, mixed-backend layouts, functional data binding,
> the lazy data layer, Datashader, reactive signals, and the HoloViews/hvplot
> adapter) is built and covered by **~330 passing tests** across macOS/Linux/Windows
> × Python 3.11–3.13. The `webengine` backend (Plotly, plus `RawFigure` passthrough
> for existing Plotly/Bokeh/HoloViews figures) is in too; only its large-payload
> binary-transport tail is still in flight. Not yet on PyPI; APIs may still change.

---

## Why qtviz?

Most Python plotting either targets the browser (Plotly, Bokeh, HoloViz) or gives
you one rendering engine bolted into Qt (matplotlib's `FigureCanvas`, raw
pyqtgraph). qtviz takes a different position:

- **One immutable API, many backends.** An `Element` is pure, value-hashed data —
  it says *what* to plot, never *how*. Write `Scatter(table, x="t", y="v")` once
  and render it native, publication-grade, or web. Pick per view, swap at runtime,
  or mix backends in a single window.
- **Native Qt, not a web app in disguise.** The default backends are real
  `QWidget`s with Qt signals/slots and strict GUI-thread discipline — no browser,
  no JavaScript bridge, no server. They feel like the desktop because they are the
  desktop.
- **Runs 100% offline.** No network at render time, ever — a hard requirement, not a
  default you can flip. The native backends draw in-process; the webengine backend
  bundles its JavaScript locally (from the installed `plotly`/`bokeh` packages, never
  a CDN). Built for air-gapped and firewalled environments.
- **Engineered for large data.** The data layer is container-agnostic and
  lazy-first — dict / NumPy / pandas / Arrow eagerly, **Dask / xarray / zarr**
  out-of-core — and integrates **Datashader** so 10M+ points become a
  screen-resolution density raster that re-aggregates to your viewport as you zoom.
  All of it resolves off the GUI thread, so the UI never stalls.
- **Functional data binding.** Channels bind to a column name, a serializable
  **expression**, a callable, or a raw array — derive a channel without first
  reshaping your data, and let expressions push down into the lazy container.
- **No dead ends.** When you need something qtviz doesn't natively model — a 3-D
  surface, a Sankey, a bespoke Plotly figure — wrap it in `RawFigure` and host it
  in the same `View`. You are never blocked waiting on the library.
- **A small surface you can hold in your head.** Five concepts — `Element`,
  composition (`*` / `+`), `View`, `Theme`, typed events — cover the whole library.
  Hello-world is six lines; a linked three-panel dashboard is under sixty.

---

## Installation

`pyqtgraph` and `numpy` are the only hard dependencies; everything else is an
opt-in extra.

```bash
git clone https://github.com/markjajeh/qtviz
cd qtviz

# core + the bits you want:
uv sync --extra matplotlib --extra dev          # the matplotlib backend
uv sync --extra webengine                       # webengine backend (Plotly/Bokeh/HoloViews)
uv sync --extra datashader --extra dask         # big-data + out-of-core
```

| Extra | Adds |
|-------|------|
| `matplotlib` | the matplotlib backend (vector PNG/SVG/PDF export) |
| `webengine` | the webengine backend — Plotly, Bokeh, HoloViews in a Qt WebEngine view |
| `datashader` | Datashader rasterization for 10M+ point/line plots |
| `dask`, `xarray` | out-of-core lazy data sources |
| `dev` | pytest, pytest-qt, ruff |

---

## A tour of the API

Everything below is real, runnable code. The point is how little of it there is.

**Elements** — eight immutable plot types, each pure data:

```python
qv.Scatter(table, x="x", y="y")
qv.Curve(table,   x="t", y="v")
qv.Bars(table,    x="category", y="count")
qv.Histogram(table, column="value", bins=40)
qv.Heatmap(table, x="x", y="y", z="z")
qv.Image(array2d, bounds=(0, 0, 10, 10))
qv.ErrorBars(table, x="x", y="y", err="sigma")
qv.Spread(table, x="t", y_lo="lo", y_hi="hi")   # filled confidence band
```

**Composition** — build a figure tree with two operators:

```python
scatter * curve                 # Overlay: same axes, layered
scatter + histogram             # Layout: side-by-side panels
qv.Layout([a, b, c], kind="tabs")                 # or "grid" | "splitter" | "dock"
qv.Layout([a, b], options=qv.LayoutOptions(cols=2, link_x=True))   # shared X axis
```

**Views & backends** — a `View` is a `QWidget`; choose an engine or let qtviz pick:

```python
view = qv.View(scatter * curve, backend="auto")   # "pyqtgraph" | "matplotlib" | "webengine"
view.set_backend("matplotlib")                     # swap at runtime — keeps zoom + subscriptions
```

**Typed events** — subscribe with `view.on(...)`; payloads are plain dataclasses:

```python
view.on(qv.SelectEvent, lambda e: print(e.indices, e.bounds))  # brush → row indices
view.on(qv.PickEvent,   lambda e: print(e.point_index, e.x, e.y))
view.on(qv.RangeEvent,  lambda e: print(e.x, e.y))             # pan/zoom (throttled)
view.on(qv.HoverEvent,  on_hover)
```

**Theming** — one `Theme` styles every backend:

```python
qv.View(scatter, theme=qv.Theme.dark())
qv.View(scatter, theme=qv.Theme.from_qt_app())     # match the host app's light/dark mode
```

---

## Working with data

### Accessors — bind channels however you like

A channel (`x`, `y`, `z`, …) binds to an **accessor**, resolved against your data
at render time:

```python
qv.Scatter(df, x="time", y="temp")                          # a column name
qv.Curve(df,   x="time", y=qv.col("raw") - qv.col("base"))  # an Expression (derived, lazy)
qv.Curve(df,   x="time", y=lambda d: d["raw"].cumsum())     # a callable (arbitrary Python)
qv.Scatter({}, x=np.linspace(0, 1, n), y=values)            # literal arrays
```

A **column name** is the easy default. An **`Expression`** (`qv.col(...)` plus
arithmetic and transforms) is serializable, introspectable, and lazy — the
underlying container does the work, so it pushes down into Dask / Parquet rather
than materializing first. A **callable** is the escape hatch for anything else. A
**literal array** is just the values.

### Color & size encoding — with automatic legends

Bind `color_by` / `size_by` to a column and qtviz maps it to per-point color or
size and adds the matching key automatically — a categorical column becomes a
color legend, a numeric column a continuous ramp plus colorbar:

```python
qv.Scatter(df, x="x", y="y", color_by="category")    # categorical → key legend
qv.Scatter(df, x="x", y="y", color_by="magnitude")   # numeric → ramp + colorbar
qv.Scatter(df, x="x", y="y", size_by="magnitude")    # per-point size
```

It is the same data-to-color rule the Datashader path uses, so a column colors
consistently however it is drawn, on any backend.

### Big data — Datashader

Past a few hundred thousand points a scatter overplots into a featureless blob.
Set `scale="datashader"` and qtviz aggregates the points into a
screen-resolution density raster off the GUI thread — and **re-aggregates to the
visible viewport at your widget's pixel size as you pan and zoom**, so the image
sharpens rather than pixelating:

```python
qv.Scatter(big, x="x", y="y", scale="datashader")                  # point density
qv.Curve(series, x="t", y="v", scale="datashader")                 # line density (huge series)
qv.Scatter(big, x="x", y="y", color_by="z",   scale="datashader")  # mean of z per pixel
qv.Scatter(big, x="x", y="y", color_by="cat", scale="datashader")  # per-category blend
qv.Scatter(big, x="x", y="y", scale="auto")                        # rasterize past a threshold
qv.set_raster_threshold(2_000_000)                                 # tune the "auto" cutoff
```

Rasterization is a **backend-agnostic pipeline step**, so every backend draws a
datashaded plot, and it is **out-of-core**: backed by a lazy Dask / xarray / zarr
source, the data is aggregated partition-by-partition and the full table never
lands in memory.

---

## Backends

| Backend | Best for | Notes |
|---------|----------|-------|
| **pyqtgraph** | real-time, interactive, large data | default; OpenGL; no extra deps |
| **matplotlib** | figures for print / papers | optional extra; PNG / SVG / PDF export |
| **webengine** | rich interactive web charts, escape hatch | optional extra; Plotly traces in a Qt WebEngine view |

Backends are **registered, never imported by the core**, so adding one touches
only its own directory and the rest of the library is none the wiser.
`View(root, backend=...)` accepts a name, a `Backend`, or `"auto"`; negotiation
resolves an engine per node from backend hints, capabilities, and data size.

### webengine + `RawFigure` — your existing figures, hosted

The `webengine` backend renders the same eight Elements as interactive Plotly
charts inside an embedded `QWebEngineView`, bridging Plotly's interactions back as
the *same* typed qtviz events the native backends emit. And when you have a figure
qtviz doesn't natively model, `RawFigure` hosts it unchanged:

```python
import plotly.graph_objects as go

fig = go.Figure(go.Surface(z=heights))            # a 3-D surface — beyond the 2-D vocabulary
view = qv.View(qv.RawFigure(fig))                 # auto-routes to webengine
view.on(qv.PickEvent, on_pick)                    # Plotly events still arrive as qtviz events
```

`RawFigure` auto-detects Plotly, Bokeh, or HoloViews and hosts each through the
appropriate renderer — so the native HoloViews/Bokeh ecosystems remain one line
away whenever you need them.

> The `webengine` backend needs the `webengine` extra and a real display (a
> `QWebEngineView` is not usable under headless/offscreen Qt). The native
> pyqtgraph and matplotlib backends have no such constraint.

---

## Examples

Self-contained, runnable scripts live in [`examples/`](examples) — each exposes a
`build()` (returns the widget) and a `main()` (shows a window):

```bash
uv run python examples/01_hello.py
```

**Native:** `01_hello` · `02_composition` · `03_backends` (switch live) ·
`04_theming` · `05_interaction` · `06_data_binding` · `07_mixed_backends` ·
`08_gallery` (all eight elements) · `09_datashader` (millions of points,
re-aggregated on zoom) · `10_out_of_core` (lazy Dask) · `11_datashader_matplotlib`
· `12_color_mapping` · `25_raster_inspect` (hover a datashaded plot for the count
under the cursor) · `dashboard_native` (3-panel linked dashboard).

**Reactive & adapter:** `21_reactive_crossfilter` (brush one view → a `Signal`
re-renders another) · `22_from_holoviews` (render a HoloViews tree natively) ·
`23_from_holoviews_dynamicmap` (drive a `DynamicMap` with a Qt control) ·
`24_from_hvplot` (a pandas `.hvplot` one-liner as a native widget).

**Real-world scenarios:** `26_telemetry_monitoring` (rolling baseline, tolerance band,
flagged anomalies, residual panel) · `27_market_analytics` (price + moving averages +
Bollinger band over a linked volume panel) · `28_event_density_map` (2M categorized
events, Datashaded, hover for counts) · `29_climate_field` (an `xarray` 2-D field as an
`Image` map + a 1-D cross-section) · `30_xarray_sensor_lines` (a 3-D `xarray` cube →
all instance lines for one sensor).

**webengine:** `13_webengine` · `14_webengine_overlay` · `15_webengine_elements` ·
`16_webengine_export` (PNG) · `17_webengine_heatmap` · `18_webengine_raw_figure`
(host a Plotly 3-D surface) · `19_webengine_holoviews` · `20_mixed_native_web`.

See [`examples/README.md`](examples/README.md) for the full index.

---

## What works today

| Area | Support |
|------|---------|
| **Backends** | pyqtgraph (native, default) · matplotlib (extra) · webengine / Plotly (extra) |
| **Elements** | Scatter · Curve · Bars · Histogram · Image · Heatmap · ErrorBars · Spread · `RawFigure` (passthrough) |
| **Composition** | Overlay (`*`) · Layout (`+`): grid / splitter / tabs / dock · mixed-backend panes |
| **Data binding** | accessors: column name · `Expression` (`col`, arithmetic, transforms) · callable · literal array |
| **Encoding** | `color_by` (categorical key · continuous ramp) · `size_by` · **automatic legend / colorbar** |
| **Data inputs** | dict · NumPy · pandas · Arrow (eager) · **Dask · xarray · zarr** (out-of-core, off-thread) · `qv.tabular()` / `qv.gridded()` shape overrides |
| **Big data** | **Datashader** — `Scatter` / `Curve` with `scale="datashader" \| "auto"`: density · `color_by` mean · categorical blend; out-of-core, off-thread, re-aggregating to the viewport on zoom; **hover a raster for the aggregated value** (`HoverEvent.value`) |
| **Interaction** | pan / zoom · brush-select (Shift-drag) · pick · hover · tap · linked axes · typed events via `View.on` |
| **HoloViews / hvplot** | `from_holoviews(obj)` translates a HoloViews tree to native Elements (8 elements + containers; `RawFigure` fallback) · `DynamicMap` → `Signal[Node]` (kdim-driven re-render) · `from_hvplot(df, kind, …)` one-liner |
| **Reactive** | `signal` / `derived` / `effect` / `batch` (S-style auto-tracking) · `View(Signal[Node])` re-renders on change · crossfilter / linked brushing |
| **Theming** | `Theme.light()` / `dark()` / `from_qt_app()` · `Color` · `Palette` |
| **Lifecycle** | runtime backend switching · auto backend selection · live theme/data updates · async render for lazy data |
| **Export** | PNG (pyqtgraph) · PNG / SVG / PDF (matplotlib) · PNG (webengine) |

---

## Roadmap

qtviz is built in phases toward a `0.1` release. The native library and the
big-data path are done; the webengine backend and the reactive/data-source layers
are the current frontier.

### Shipped

- ✅ **Core data model + composition + pyqtgraph backend** — immutable `Element`,
  `Overlay`/`Layout`, typed event bus, the eight-element vocabulary.
- ✅ **matplotlib backend** — the same Elements as static, vector-exportable figures.
- ✅ **Mixed-backend layouts** — a pyqtgraph pane beside a matplotlib pane, one
  merged event stream.
- ✅ **Functional data binding** — accessors (column / `Expression` / callable /
  array) with projection pushdown.
- ✅ **Lazy, out-of-core data layer** — Dask / xarray / zarr adapters, resolved
  off the GUI thread.
- ✅ **Datashader** — 10M+ point/line rasterization with viewport re-aggregation,
  out-of-core, backend-agnostic.
- ✅ **Color / size encoding** — `color_by` / `size_by` with automatic legends and
  colorbars.
- ✅ **Reactive `Signal` binding** — S-style `signal` / `derived` / `effect` / `batch`;
  `View(Signal[Node])` re-renders on change; linked brushing / crossfilter falls out
  of `Signal` + `derived` + `View.on` (no manual wiring).
- ✅ **HoloViews / hvplot adapter** — `from_holoviews(obj)` translates a HoloViews
  tree to native Elements (`RawFigure` fallback for the long tail); `DynamicMap` →
  `Signal[Node]` one-way re-render; `from_hvplot(df, kind, …)` one-liner.
- ✅ **Raster hover-inspect** — hovering a datashaded view reports the aggregated
  `count` / `mean` under the cursor via `HoverEvent.value`, fresh through pan/zoom.

### In progress — the webengine backend (Phase 5)

- ✅ Rehomed the legacy Qt↔JS bridge under `qtviz.backends.webengine`.
- ✅ Render all eight Elements as Plotly charts; typed events; PNG export.
- ✅ `RawFigure` passthrough — host any existing Plotly / Bokeh / HoloViews figure;
  per-element selection routing.
- ✅ Bokeh / HoloViews event translation — passthrough Bokeh and HoloViews figures
  emit qtviz typed events (tap / select / range).
- ✅ Mixed native + webengine panes in one `Layout`, sharing one event stream.
- ✅ Binary (base64 typed-array) transport for large Plotly payloads — ~4× faster
  serialize at 1M points.
- ◻ True-binary `fetch` transport (custom URL scheme) for the extreme (100 MB+) tail.

### Planned

- ◻ **Data sources** — Parquet / DuckDB / SQL behind the lazy data contract, with
  background queries and a versioned result cache.
- ◻ **Axis transforms** — log / symlog / datetime scales across all backends.
- ◻ **Raster selection** — brush / linked-select on a datashaded view (pixel → source
  rows), building on the hover reverse-lookup already shipped.
- ◻ **`qtviz 0.1` on PyPI** — release prep is done (versioned metadata, an mkdocs docs
  site, the examples gallery, a migration note, and a CHANGELOG); the PyPI publish and
  docs-site deploy are the remaining steps.

### Exploring

- ◻ **qtviz Studio** — a desktop application built on the library: sources, canvas,
  inspector, and pipeline, with selectable backends per plot.

The living plan — with rationale and trade-offs — is in
[`design/roadmap.md`](design/roadmap.md) and
[`design/discussion-items.md`](design/discussion-items.md).

---

## Architecture

```
Element (pure data)
    │  negotiation picks a Backend from hints + capabilities + data size
    ▼
resolve pipeline  ── turns channel accessors into role-keyed arrays
    │                (off the GUI thread for lazy / datashaded data)
    ▼
Backend renderers ── build native primitives (pyqtgraph items, mpl artists,
    │                Plotly traces)
    ▼
RenderHandle ── owns the QWidget and a typed EventBus; survives backend swaps
```

Both **backends and data adapters are registered, never imported by the core**, so
every new engine or container type is purely additive. The design documents —
specification, development plan, milestone notes, and the full decision log — live
in [`design/`](design/).

---

## Migrating from `qtwebplot`

qtviz began as `qtwebplot`; the Qt↔JS bridge now lives under
`qtviz.backends.webengine`. Existing `import qtwebplot` code keeps working through a
compatibility shim that transparently redirects to the new location and emits a
`DeprecationWarning`. Update imports to `qtviz.backends.webengine` (or the public
`qtviz` API) when convenient — the shim is kept for two releases, then removed.

---

## Contributing

qtviz is pre-release and evolving quickly. Issues and discussion are welcome on
[GitHub](https://github.com/markjajeh/qtviz). Run the suite with:

```bash
uv run pytest          # Qt runs offscreen by default
uv run ruff check src
```

---

## License

[MIT](LICENSE)
