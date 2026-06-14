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
| — | [`dashboard_native.py`](dashboard_native.py) | 3-panel linked dashboard (shared X, brushing, dark theme). |

More examples will be added as the library grows (lazy/out-of-core data,
reactive signals, the HoloViews adapter, …).

The [`webengine/`](webengine) folder holds the legacy `qtwebplot` (Qt WebEngine +
Plotly/Bokeh/HoloViews) examples — that path becomes the future `webengine`
backend (roadmap Phase 5).
