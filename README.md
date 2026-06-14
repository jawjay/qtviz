# qtviz

Native-Qt declarative plotting. One small, immutable API renders the same plot
through multiple backends — **pyqtgraph** (fast, OpenGL, interactive) and
**matplotlib** (publication-quality, vector export) today — and drops straight
into any PySide6 app as a `QWidget`.

> **Status: in active development (pre-release).** The Phase 1 surface
> (data model, two backends, interaction, mixed-backend layouts) works and is
> covered by ~100 tests. Not yet on PyPI; APIs may still change.
>
> qtviz began as `qtwebplot` (Qt WebEngine + JS libraries); that path is being
> rehomed as a future `webengine` backend — see the roadmap.

## Why

- **Declarative + immutable.** `Element` is pure data; describe *what*, not how.
- **Multi-backend.** The same `Scatter(...)` renders through pyqtgraph or
  matplotlib — switch at runtime, or let qtviz auto-pick by data size.
- **Native Qt.** Real `QWidget`s, signals/slots, GUI-thread discipline — no
  browser, no JS bridge for the native backends.
- **Container-agnostic data.** Bind a `dict`, numpy array, pandas DataFrame, or
  Arrow table — with xarray/zarr/Dask planned, lazy-first.

## Install (from source)

pyqtgraph is a core dependency; matplotlib is an optional extra.

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

## Examples

These assume a `data` dict with a few numeric columns (e.g. `x`, `t`, `y`,
`signal`, `noisy`); wrap each snippet in the `QApplication` boilerplate above to run.

**Compose** — overlay with `*` (same axes), lay out with `+` (side by side):

```python
overlay = qv.Scatter(data, x="x", y="noisy") * qv.Curve(data, x="x", y="signal")
side_by_side = qv.Scatter(data, x="x", y="y") + qv.Histogram(data, column="y")
```

**Theme** — match a dark host app:

```python
view = qv.View(overlay, theme=qv.Theme.dark())     # or Theme.from_qt_app()
```

**Choose / switch backends** at runtime:

```python
view = qv.View(root, backend="matplotlib")   # "pyqtgraph" | "matplotlib" | "auto"
view.set_backend("pyqtgraph")                # preserves zoom + subscriptions
```

**Interact** — subscribe to typed events (pan/zoom, Shift-drag to brush-select):

```python
view = qv.View(qv.Scatter(data, x="x", y="y"))
view.on(qv.SelectEvent, lambda e: print(f"brushed {len(e.indices)} points"))
view.on(qv.RangeEvent,  lambda e: print("viewport:", e.x))
```

**Linked panels** — shared X axis across a grid:

```python
dash = qv.Layout(
    [qv.Scatter(data, x="t", y="noisy"), qv.Curve(data, x="t", y="signal")],
    options=qv.LayoutOptions(cols=2, link_x=True),
)
```

**Mixed backends in one window** — a pyqtgraph pane beside a matplotlib pane:

```python
mixed = qv.Layout(
    [qv.Scatter(data, x="x", y="y", backend_hint="pyqtgraph"),
     qv.Curve(data,   x="x", y="y", backend_hint="matplotlib")],
    kind="splitter",   # or "tabs" | "dock" | "grid"
)
# view.on(...) still sees one merged event stream across both panes.
```

A runnable 3-panel dashboard lives in [`examples/dashboard_native.py`](examples/dashboard_native.py).

## What works today

| Area | Support |
|------|---------|
| **Backends** | pyqtgraph (native, default) · matplotlib (optional extra) |
| **Elements** | Scatter · Curve · Bars · Histogram · Image · Heatmap · ErrorBars · Spread |
| **Composition** | Overlay (`*`) · Layout (`+`): grid / splitter / tabs / dock · mixed-backend panes |
| **Data inputs** | dict · numpy · pandas · Arrow (container-agnostic, named columns) |
| **Interaction** | pan / zoom · brush-select (Shift-drag) · pick · hover · tap · linked axes · typed events via `View.on` |
| **Theming** | `Theme.light()` / `dark()` / `from_qt_app()` · `Color` · `Palette` |
| **Lifecycle** | runtime backend switching · auto backend selection · live theme/data updates |
| **Export** | PNG (pyqtgraph) · PNG / SVG / PDF (matplotlib) |

## Roadmap

| Phase | Item | Status |
|-------|------|--------|
| 1 | Core data model + composition + **pyqtgraph** backend | ✅ done |
| 2 | **matplotlib** backend | ✅ done |
| — | Mixed-backend layouts + native interaction | ✅ done |
| 3 | **HoloViews adapter** (`from_holoviews`) | planned |
| 4 | **Reactive** `Signal` binding · **Datashader** for 10M+ points | planned |
| 5 | **Data sources** (Parquet / DuckDB / Dask) · lazy xarray/zarr/Dask adapters · **webengine** backend rehome (Plotly/Bokeh) | planned |
| 6 | Docs, gallery, **`qtviz 0.1` on PyPI** | planned |
| 7+ | **qtviz Studio** — a desktop app on top of the library | exploring |

The data layer is lazy-first by design, so out-of-core containers (Dask, zarr)
and query-backed sources slot in as adapters without changing the Element API.

## Architecture

`Element` (pure data) → negotiation picks a `Backend` → the backend's renderers
build native primitives → a `RenderHandle` owns the `QWidget` and a typed
`EventBus`. Backends are registered, never imported by the core, so adding one
touches only its own directory. Design docs live in [`design/`](design/)
(`spec.md`, `development-plan.md`, `roadmap.md`).

## License

MIT
