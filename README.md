# qtwebplot

PySide6 widgets and utilities for embedding modern Python plotting libraries
(Plotly, Bokeh, HoloViews, …) inside Qt applications via Qt WebEngine.

Status: **early scaffold** — APIs are not stable.

## Goals

- Low friction: drop a plot into a `QWidget` with one or two lines.
- Backend-agnostic core: same widget surface for Plotly / Bokeh / HoloViews / raw HTML.
- Bidirectional bridge: Python ⇄ JS via `QWebChannel` so Qt code can react to
  selections, hovers, and clicks.
- Fast iteration: efficient updates without full-page reloads where possible.
- Sensible defaults, escape hatches everywhere.

## Install (dev)

```bash
uv sync --extra dev --extra all
```

## Layout

```
src/qtwebplot/
  widgets/      # QWidget subclasses (PlotView, etc.)
  backends/     # Per-library adapters (plotly, bokeh, holoviews)
  bridge/       # QWebChannel <-> JS plumbing
  utils/        # HTML templating, asset helpers, etc.
```

## License

MIT
