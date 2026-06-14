# qtviz

Native-Qt declarative plotting. One small, immutable API renders the same plot
through multiple backends — **pyqtgraph** (fast, OpenGL, interactive) and
**matplotlib** (publication-quality, vector export) today — and drops straight
into any PySide6 app as a `QWidget`.

> **Status: in active development (pre-release).** The Phase 1 surface (data
> model, two native backends, interaction, mixed-backend layouts, functional
> data binding) works and is covered by ~110 tests. Not yet on PyPI; APIs may
> still change.
>
> qtviz began as `qtwebplot` (Qt WebEngine + JS libraries); that path is being
> rehomed as a future `webengine` backend — see the roadmap.

## Why

- **Declarative + immutable.** An `Element` is pure data — it describes *what*
  to plot, not how. The same Element renders identically across backends.
- **Multi-backend.** One `Scatter(...)` renders through pyqtgraph or matplotlib;
  switch at runtime, mix them in one window, or let qtviz auto-pick by data size.
- **Native Qt.** Real `QWidget`s, signals/slots, GUI-thread discipline — no
  browser, no JS bridge for the native backends.
- **Functional data binding.** Channels bind to column names, serializable
  **expressions**, callables, or raw arrays — so deriving a channel never means
  reshaping your data first.
- **Data-intensive by design.** The data layer is container-agnostic and
  lazy-first: dict / numpy / pandas / Arrow today; xarray / zarr / Dask resolve
  off the GUI thread without changing the Element API (in progress).

## Install (from source)

`pyqtgraph` + `numpy` are core dependencies; `matplotlib` is an optional extra.

```bash
git clone https://github.com/markjajeh/qtviz
cd qtviz
uv sync --extra matplotlib --extra dev
```

## Quick start

```python
import numpy as np
from PySide6.QtWidgets import QApplication
import qtviz as qv

app = QApplication([])
x = np.linspace(0, 10, 500)
data = {"x": x, "y": np.sin(x)}

view = qv.View(qv.Scatter(data, x="x", y="y"))   # backend="auto" by default
view.show()
app.exec()
```

## Concepts

### Elements
An `Element` is immutable, value-hashed, Qt-free data: `Scatter`, `Curve`,
`Bars`, `Histogram`, `Image`, `Heatmap`, `ErrorBars`, `Spread`. It carries its
data binding and styling and nothing about rendering — backends know how to draw
each type.

### Data binding — accessors
A channel (`x`, `y`, `z`, …) binds to an **accessor**, resolved against your data:

```python
qv.Scatter(df, x="time", y="temp")                       # column name
qv.Curve(df,  x="time", y=qv.col("raw") - qv.col("base")) # Expression (derived)
qv.Curve(df,  x="time", y=lambda d: d["raw"].cumsum())    # callable (arbitrary Python)
qv.Scatter({}, x=np.linspace(0, 1, n), y=values)          # literal arrays
```

- a **column name** is the easy default;
- an **`Expression`** (`qv.col(...)` + arithmetic / transforms) is serializable,
  introspectable, and lazy — the underlying container does the work, so it pushes
  down to dask/Parquet;
- a **callable** is the escape hatch for anything else;
- a **literal array** is just the values.

### Composition
Operators build a figure tree:

```python
a * b   # Overlay — same axes, layered
a + b   # Layout  — side-by-side panels (grid)
qv.Layout([a, b], kind="splitter")        # or "tabs" | "dock" | "grid"
qv.Layout([a, b], options=qv.LayoutOptions(cols=2, link_x=True))   # shared X axis
```

An `Overlay` resolves to a single backend; a `Layout` may mix backends per pane.

### Backends & negotiation
`View(root, backend=...)` takes `"pyqtgraph"`, `"matplotlib"`, a `Backend`, or
`"auto"`. Negotiation resolves a backend per node from hints + capabilities;
`view.set_backend(...)` swaps at runtime, preserving zoom and subscriptions.
Backends are registered, never imported by the core, so adding one touches only
its own directory.

### Views & events
A `View` is a `QWidget`. Subscribe to typed, throttled events:

```python
view.on(qv.SelectEvent, on_brush)   # Shift-drag rubber-band → row indices + bounds
view.on(qv.PickEvent,   on_click)   # click a point
view.on(qv.RangeEvent,  on_zoom)    # pan/zoom (throttled)
view.on(qv.HoverEvent,  on_hover)
```

For lazy data, the materialize step runs on a worker thread and the View keeps
the last render up until the new one is ready.

### Theming
A `Theme` carries `Color`s and a `Palette`. `Theme.light()` / `dark()` are built
in; `Theme.from_qt_app()` matches the host app's light/dark mode.

## Examples

Runnable, self-contained scripts in [`examples/`](examples) — each has a
`build()` (returns the widget) and a `main()` (shows a window):

```bash
uv run python examples/01_hello.py
```

`01_hello` · `02_composition` · `03_backends` · `04_theming` · `05_interaction`
· `06_data_binding` · `07_mixed_backends` · `08_gallery` · `dashboard_native`
(3-panel linked dashboard). See [`examples/README.md`](examples/README.md).

## What works today

| Area | Support |
|------|---------|
| **Backends** | pyqtgraph (native, default) · matplotlib (optional extra) |
| **Elements** | Scatter · Curve · Bars · Histogram · Image · Heatmap · ErrorBars · Spread |
| **Composition** | Overlay (`*`) · Layout (`+`): grid / splitter / tabs / dock · mixed-backend panes |
| **Data binding** | accessors: column name · `Expression` (`col`, arithmetic, transforms) · callable · literal array |
| **Data inputs** | dict · numpy · pandas · Arrow (container-agnostic) |
| **Interaction** | pan / zoom · brush-select (Shift-drag) · pick · hover · tap · linked axes · typed events via `View.on` |
| **Theming** | `Theme.light()` / `dark()` / `from_qt_app()` · `Color` · `Palette` |
| **Lifecycle** | runtime backend switching · auto backend selection · live theme/data updates · async render for lazy data |
| **Export** | PNG (pyqtgraph) · PNG / SVG / PDF (matplotlib) |

## Roadmap

| Phase | Item | Status |
|-------|------|--------|
| 1 | Core data model + composition + **pyqtgraph** backend | ✅ done |
| 2 | **matplotlib** backend | ✅ done |
| — | Mixed-backend layouts · native interaction · functional data binding | ✅ done |
| 4–5 | **Lazy adapters** (xarray / zarr / Dask) · **Datashader** for 10M+ points · **Reactive** `Signal` binding | in progress |
| 5 | **Data sources** (Parquet / DuckDB / Dask) · **webengine** backend rehome (Plotly/Bokeh) | planned |
| 3 | **HoloViews adapter** (`from_holoviews`) | planned |
| 6 | Docs, gallery, **`qtviz 0.1` on PyPI** | planned |
| 7+ | **qtviz Studio** — a desktop app on top of the library | exploring |

## Architecture

`Element` (pure data) → negotiation picks a `Backend` → the resolve pipeline
turns channel accessors into arrays (off-thread for lazy data) → the backend's
renderers build native primitives → a `RenderHandle` owns the `QWidget` and a
typed `EventBus`. Backends and data adapters are both registered, never imported
by the core, so each new one is additive. Design docs live in
[`design/`](design/) (`spec.md`, `development-plan.md`, `roadmap.md`,
`milestone-*.md`, `discussion-items.md`).

## License

MIT
