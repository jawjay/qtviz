"""RawFigure — host an existing Plotly figure qtviz doesn't natively model.

`qv.RawFigure(fig)` is the escape hatch (D26): wrap any existing Plotly / Bokeh /
HoloViews figure and drop it into a qtviz `View`. It negotiates only to the
webengine backend (no native backend can render it), and a Plotly raw figure
still bridges Plotly's interactions back as qtviz typed events — so
`view.on(PickEvent, ...)` works on a figure qtviz never built.

Here a 3-D `go.Surface` — well outside qtviz's 2-D element vocabulary — is hosted
directly. `backend="auto"` resolves to webengine because that's the only backend
that supports a RawFigure.

Needs a real display plus the webengine extra (`pip install "qtviz[webengine]"`)
and renders fully offline (JS bundled, no CDN); it will not run headless.

Run:
    uv run python examples/18_webengine_raw_figure.py
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

import qtviz as qv


def build():
    x = np.linspace(-3, 3, 80)
    y = np.linspace(-3, 3, 80)
    gx, gy = np.meshgrid(x, y)
    z = np.sin(np.sqrt(gx**2 + gy**2)) * np.exp(-(gx**2 + gy**2) / 10)

    fig = go.Figure(go.Surface(z=z, colorscale="Viridis"))
    fig.update_layout(title="a Plotly 3-D surface, hosted in qtviz")

    view = qv.View(qv.RawFigure(fig))  # backend="auto" → webengine (only supporter)
    view.on(qv.PickEvent, lambda e: print(f"picked at ({e.x:.2f}, {e.y:.2f})"))
    return view


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build, title="qtviz — RawFigure (Plotly 3-D surface)", size=(860, 640))


if __name__ == "__main__":
    main()
