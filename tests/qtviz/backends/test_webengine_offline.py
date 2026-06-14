"""W5 offline — the webengine backend renders with no network (spec §0.1, D37).

Headless: `to_html` is pure Python, so these run in the default suite (no display).
The check is for external resource **tags** (`<script src>` / `<link href>` /
`<img src>` to `http(s)://`) — i.e. things the page would actually *fetch*. URL
*strings* inside the inlined JS (plotly's map-tile defaults, bokeh's lazy MathJax
loader) are not fetched for our element vocabulary and are correctly ignored.

Out of scope (would fetch, by the underlying library, only if used): LaTeX axis
labels (MathJax) and map/tile traces — neither is part of the Phase-1 elements.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap

import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("plotly")

from qtviz.backends.webengine import _figure  # noqa: E402
from qtviz.backends.webengine.ext.plotly.backend import PlotlyBackend  # noqa: E402

pytestmark = pytest.mark.tier1

_EXTERNAL_TAG = re.compile(
    r"""<(?:script|link|img)\b[^>]*\b(?:src|href)\s*=\s*["'](https?://[^"']+)""",
    re.I,
)


def _external(html: str) -> list[str]:
    return sorted({m.group(1) for m in _EXTERNAL_TAG.finditer(html)})


def test_plotly_js_is_inlined_not_cdn():
    fig, _ = _figure.build(qv.Scatter({"x": [0, 1, 2], "y": [0, 1, 4]}, x="x", y="y"),
                           qv.Theme.light())
    html = PlotlyBackend(fig).to_html()
    assert _external(html) == []            # no external <script src>/<link> — no CDN
    assert len(html) > 1_000_000            # the plotly.js bundle is inlined (~3.5 MB)


def test_every_element_renders_with_no_external_resources(make_elements):
    for name, el in make_elements(qv).items():
        html = PlotlyBackend(_figure.build_figure(el, qv.Theme.light())).to_html()
        assert _external(html) == [], f"{name} fetches external resources: {_external(html)}"


def test_raw_plotly_figure_is_offline():
    go = pytest.importorskip("plotly.graph_objects")
    html = PlotlyBackend(go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 4, 9]))).to_html()
    assert _external(html) == []


def test_bokeh_figure_is_offline():
    bk = pytest.importorskip("bokeh.plotting")
    from qtviz.backends.webengine.ext.bokeh.backend import BokehBackend  # noqa: PLC0415

    fig = bk.figure()
    fig.scatter([1, 2, 3], [1, 4, 9])
    html = BokehBackend(fig).to_html()
    assert _external(html) == [], f"bokeh fetches external resources: {_external(html)}"


# Regression (the offline-inlined page must actually LOAD, not just be CDN-free):
# inlining plotly.js (~3.5 MB) blows past QWebEngineView.setHtml()'s ~2 MB cap, so
# the page must load from a temp file via setUrl() or it renders blank. Run in a
# subprocess so the offscreen QWebEngine teardown segfault can't flake the suite.
_LOAD_PROBE = textwrap.dedent(
    """
    import os, sys
    import numpy as np
    import plotly.graph_objects as go
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    import qtviz as qv
    import qtviz.backends as B

    app = QApplication.instance() or QApplication([])
    fig = go.Figure(go.Surface(z=np.random.default_rng(0).random((60, 60))))
    handle = B.get("webengine").render(qv.RawFigure(fig), theme=qv.Theme.light())
    view = handle.widget
    assert view._temp_html is not None, "large offline page should load via a temp file"
    loop, res = QEventLoop(), {}
    view.load_finished.connect(lambda ok: (res.setdefault("ok", ok), loop.quit()))
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    print("LOADED" if res.get("ok") else f"NOTLOADED:{res.get('ok')}")
    sys.stdout.flush()
    os._exit(0)
    """
)


def test_inline_offline_page_actually_loads():
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    result = subprocess.run(
        [sys.executable, "-c", _LOAD_PROBE],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert "LOADED" in result.stdout, (
        "the offline-inlined webengine page failed to load (blank render)\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr[-2000:]}"
    )
