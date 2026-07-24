# qtviz

**Declarative, native-Qt plotting for data-intensive desktop apps.**

Describe a plot once as immutable data, then render it through whichever engine fits
the moment — **pyqtgraph** (fast, OpenGL, interactive), **matplotlib**
(publication-quality, vector export), or **webengine** (interactive Plotly in an
embedded browser view). The same `Element` draws identically on all three, swaps
backends at runtime, and drops into any PySide6 application as a plain `QWidget`.

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

![A scatter plot rendered by qtviz in a native Qt window](images/examples/01_hello.png)

That is a complete program: a real Qt window, an OpenGL-accelerated scatter, pan and
zoom out of the box. Change one keyword — `backend="matplotlib"` or
`backend="webengine"` — and the same line renders through a different engine.

## Why qtviz?

- **One immutable API, many backends.** An `Element` is pure, value-hashed data — it
  says *what* to plot, never *how*. Pick a backend per view, swap at runtime, or mix
  backends in one window.
- **Native Qt, not a web app in disguise.** The default backends are real `QWidget`s
  with Qt signals/slots and strict GUI-thread discipline.
- **Runs 100% offline.** No network at render time, ever — a hard requirement. The
  webengine backend bundles its JavaScript locally, never a CDN.
- **Engineered for large data.** Container-agnostic, lazy-first data layer (dict /
  NumPy / pandas / Arrow eager; Dask / xarray / zarr out-of-core) plus **Datashader**
  so 10M+ points become a screen-resolution raster that re-aggregates on zoom.
- **No dead ends.** Wrap anything qtviz doesn't natively model in `RawFigure` and host
  it in the same `View`.

## Install

```bash
git clone https://github.com/jawjay/qtviz && cd qtviz
uv sync --extra matplotlib --extra dev        # add backends/data extras as needed
```

`pyqtgraph` and `numpy` are the only hard dependencies; everything else
(`matplotlib`, `webengine`, `datashader`, `dask`, `xarray`, `holoviews`, `hvplot`) is
an opt-in extra.

![Three-panel linked dashboard with shared X axis, brushing, and the dark theme](images/examples/dashboard_native.png)

*A linked three-panel dashboard in under sixty lines —
[`examples/dashboard_native.py`](https://github.com/jawjay/qtviz/blob/main/examples/dashboard_native.py).*

→ Continue to the [Quickstart](quickstart.md), browse the [Gallery](gallery.md)
(a screenshot of every example), or read the [API reference](api.md).
