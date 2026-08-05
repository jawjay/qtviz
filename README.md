# qtviz

**Declarative, native-Qt plotting for data-intensive desktop apps.**

Describe a plot once as immutable data, then render it through whichever engine
fits the moment — **pyqtgraph** (fast, interactive), **matplotlib**
(publication-quality), or **webengine** (interactive Plotly in an embedded
browser view). The same plot draws identically on all three, swaps backends at
runtime, and drops into any PySide6 application as a plain `QWidget`.

[![PyPI](https://img.shields.io/pypi/v/qtviz)](https://pypi.org/project/qtviz/)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Qt](https://img.shields.io/badge/Qt-PySide6-41cd52)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Docs:** [jawjay.github.io/qtviz](https://jawjay.github.io/qtviz/) ·
**Install:** `pip install qtviz` (or `uv add qtviz`)

```python
import numpy as np
import qtviz as qv

x = np.linspace(0, 10, 500)
qv.show(qv.Scatter({"x": x, "y": np.sin(x)}, x="x", y="y"), title="hello")
```

<p align="center">
  <img src="docs/images/examples/01_hello.png" width="720"
       alt="A scatter plot rendered by qtviz in a native Qt window">
</p>

That's a complete program: a real Qt window, a hardware-accelerated scatter,
pan and zoom out of the box. Change one keyword — `backend="matplotlib"` — and
the same line renders through a different engine.

## Why qtviz?

Most Python plotting either targets the browser or bolts a single rendering
engine into Qt. qtviz takes a different position:

- **One immutable API, many backends** — an `Element` says *what* to plot,
  never *how*; render it native, publication-grade, or web, and swap at runtime.
- **Native Qt, not a web app in disguise** — real `QWidget`s, Qt signals,
  strict GUI-thread discipline.
- **Runs 100% offline** — no network at render time, ever; the webengine
  backend bundles its JavaScript from your installed packages, never a CDN.
- **Built for large data** — dict / NumPy / pandas / Arrow eagerly,
  Dask / xarray / zarr out-of-core, and Datashader turns 10M+ points into a
  density raster that re-aggregates as you zoom. All off the GUI thread.
- **No dead ends** — anything qtviz doesn't model natively (a 3-D surface, a
  Sankey) rides in through `RawFigure` in the same `View`, with the same events.

## In action

| | |
|---|---|
| <img src="docs/images/examples/26_telemetry_monitoring.png" alt="Telemetry monitoring: rolling baseline, tolerance band, flagged anomalies, linked residual panel"> *Telemetry — baseline, 3σ band, flagged anomalies, linked residual panel* | <img src="docs/images/examples/27_market_analytics.png" alt="Market analytics: price, moving averages, Bollinger band over a linked volume panel"> *Market analytics — price, MAs, Bollinger band over linked volume* |
| <img src="docs/images/examples/28_event_density_map.png" alt="2M events datashaded into a categorical density map with a legend"> *2M events, datashaded — hover reports the count under the cursor* | <img src="docs/images/examples/18_webengine_raw_figure.png" alt="A Plotly 3-D surface hosted through RawFigure in a Qt WebEngine view"> *A Plotly 3-D surface via `RawFigure` — still emitting typed qtviz events* |

Every screenshot here is captured from a runnable script — the
[gallery](https://jawjay.github.io/qtviz/gallery/) shows all 37.

## Installation

```bash
pip install qtviz                      # or:  uv add qtviz
pip install "qtviz[matplotlib]"        # + the matplotlib backend
pip install "qtviz[webengine]"         # + Plotly/Bokeh/HoloViews hosting
pip install "qtviz[all]"               # everything
```

Hard dependencies: `PySide6`, `pyqtgraph`, `numpy`. Extras: `matplotlib`,
`webengine`, `datashader`, `dask`, `xarray`, `hvplot`, `all`.

## Five concepts cover the library

### 1 · Elements are pure data

Twenty-eight immutable plot types share one channel vocabulary — data first,
then keyword accessors (a column name, a lazy expression, a callable, or an
array):

```python
qv.Scatter(df, x="time", y="temp", color_by="sensor")     # auto legend
qv.Curve(df,   x="time", y=qv.col("raw") - qv.col("base"))  # derived channel
qv.Bars(df,    x="region", y="sales", by="year", orient="horizontal")
qv.Heatmap(df, x="day", y="hour", z="load", annotate="auto")
qv.Histogram(df, value="latency", bins="fd")
qv.HLine(4.5, label="alarm") * qv.Span(2, 4) * qv.Text(5, 2, "peak")
```

<p align="center">
  <img src="docs/images/examples/35_everyday_figures.png"
       alt="The everyday figures: step curve, stacked area, horizontal bars, donut, ECDF, filled contour, SI ticks, dual axis, quiver key, mesh, stem, annotated heatmap">
</p>

*The everyday figures, declaratively — one grid, one vocabulary
([`examples/35_everyday_figures.py`](examples/35_everyday_figures.py)).*

### 2 · Compose with two operators

`*` overlays on shared axes; `+` lays out panels. Configure any node with
`.opts()` — no wrapper construction:

```python
(price * bollinger_band).opts(title="AAPL", y="USD")    # layered, labeled
price + volume                                          # side-by-side panels
qv.Layout.mosaic("AAB\nCCB", A=a, B=b, C=c).opts(link_x=True)
```

<p align="center">
  <img src="docs/images/examples/36_mosaic_layout.png" width="720"
       alt="Mosaic layout with spanning panes and a suptitle">
</p>

*Spanning panes from an ASCII plan, track ratios, and a figure suptitle.*

### 3 · A `View` is a `QWidget`

Choose an engine, let qtviz pick, or mix engines in one window — pan/zoom and
subscriptions survive a runtime swap:

```python
view = qv.View(scatter * curve, backend="auto")   # "pyqtgraph" | "matplotlib" | "webengine"
view.set_backend("matplotlib")                    # swap live — keeps zoom + events
layout.addWidget(view)                            # it's just a QWidget
```

<p align="center">
  <img src="docs/images/examples/07_mixed_backends.png" width="720"
       alt="A pyqtgraph pane and a matplotlib pane side by side in one layout">
</p>

*One `Layout`, two engines — pyqtgraph beside matplotlib, one event stream.*

### 4 · Typed events

Interactions arrive as plain dataclasses, identical on every backend:

```python
view.on(qv.SelectEvent, lambda e: print(e.indices))   # brush → row indices
view.on(qv.HoverEvent,  lambda e: print(e.value))     # aggregated value on rasters
view.on(qv.RangeEvent,  on_zoom, throttle_ms=50)
```

### 5 · One `Theme` styles every backend

```python
qv.View(plot, theme=qv.Theme.dark())
qv.View(plot, theme=qv.Theme.from_qt_app())   # match the host app's mode
```

<p align="center">
  <img src="docs/images/examples/04_theming.png" width="720"
       alt="Three overlaid curves drawn from a registered custom palette on the dark theme">
</p>

## Scale: live data and millions of points

A `qv.stream` is a thread-safe, append-able source — views update in place.
Past the point where a scatter overplots, `raster="datashader"` aggregates to
a screen-resolution density image that **re-aggregates to the viewport as you
zoom**, out-of-core when the data is lazy:

```python
feed = qv.stream({"t": float, "v": float}, window=100_000)
qv.View(qv.Curve(feed, x="t", y="v"))              # that's all the wiring
feed.append(t=ts, v=vs)                            # from any thread

qv.Scatter(big, x="x", y="y", raster="datashader")  # 10M points → density raster
```

<p align="center">
  <img src="docs/images/examples/34_streaming_telemetry.png" width="720"
       alt="A live rolling feed beside a datashaded 400k-point history and a brush-driven detail panel">
</p>

*A live rolling feed, its datashaded 400k-point history, and a brush-driven
detail panel — [`examples/34_streaming_telemetry.py`](examples/34_streaming_telemetry.py).*

## Backends

| Backend | Best for | Notes |
|---------|----------|-------|
| **pyqtgraph** | real-time, interactive, large data | default; no extra deps |
| **matplotlib** | figures for print / papers | extra; PNG / SVG / PDF export |
| **webengine** | rich web charts, escape hatch | extra; Plotly in a Qt WebEngine view |

Backends are **registered, never imported by the core** — a third-party
backend plugs in through an entry point with zero qtviz edits
([writing a backend](https://jawjay.github.io/qtviz/backends/)). The webengine
backend renders the same elements as interactive Plotly, and `RawFigure` hosts
any existing Plotly / Bokeh / HoloViews figure with events bridged back:

```python
fig = go.Figure(go.Surface(z=heights))    # beyond the 2-D vocabulary
view = qv.View(qv.RawFigure(fig))         # auto-routes to webengine
view.on(qv.PickEvent, on_pick)            # still typed qtviz events
```

## How it fits together

```
Element (pure data)
    │   negotiation picks a Backend from hints + capabilities + data size
    ▼
resolve pipeline    turns channel accessors into arrays
    │               (off the GUI thread for lazy / datashaded data)
    ▼
Backend renderers   build native primitives — pyqtgraph items,
    │               matplotlib artists, Plotly traces
    ▼
RenderHandle        owns the QWidget + a typed EventBus;
                    survives backend swaps
```

Backends *and* data adapters are registered, never imported by the core, so
every new engine or container type is purely additive. The full design record
— specification, architecture, decision log — lives in
[`design/`](design).

## Examples

37 runnable scripts in
[`examples/`](examples), from
hello-world to linked dashboards, reactive crossfilters, HoloViews/hvplot
adapters, and out-of-core xarray cubes — every one screenshotted in the
[gallery](https://jawjay.github.io/qtviz/gallery/):

```bash
uv run python examples/01_hello.py
```

<p align="center">
  <img src="docs/images/examples/dashboard_native.png" width="720"
       alt="A three-panel dashboard with a shared X axis, brushing, and the dark theme">
</p>

*The linked three-panel dashboard, under sixty lines —
[`examples/dashboard_native.py`](examples/dashboard_native.py).*

## Stability

**2.0 is the current stable release.** The 71-name public surface is frozen
under a documented policy — semver, a deprecation window, and a test suite
that pins the API, the honor-or-warn contract (an option is honored or warns,
never silently dropped), and the performance ceilings
([stability policy](https://jawjay.github.io/qtviz/stability/)). Fully typed
(`py.typed`), 980+ tests, mypy-clean.

## Contributing

Issues and PRs welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md)
for the uv-based setup, the CI gates, and the project's conventions.

## License

[MIT](LICENSE)
