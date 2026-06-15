# qtviz — an outside evaluator's assessment

*An independent review of the qtviz library's value relative to the existing Python
visualization landscape. Written from the perspective of an external evaluator, based
on (a) qtviz's own documentation and design record, and (b) web research into competing
libraries current to mid-2026.*

> **Methodology & caveats.** This assessment reads qtviz's public surface — `README.md`,
> the `design/` specification and decision log, `examples/`, and `CHANGELOG.md` — and
> compares it against researched facts about alternative libraries. I did **not** install,
> run, or independently benchmark qtviz; its capability and performance claims here are
> **self-reported** (though backed by an unusually detailed design and test record — ~331
> tests across macOS/Linux/Windows × Python 3.11–3.13, plus backend/adapter conformance
> suites). qtviz is **pre-release (`0.1.0`, alpha), not yet on PyPI**, and appears to be a
> single-maintainer project. Treat the verdict as "promising and well-engineered for its
> stage," not "production-proven."

---

## Verdict in one paragraph

qtviz occupies a **real and under-served niche**: it is, as far as this research found,
the only Python library that pairs an **immutable, declarative plot description** with a
**true multi-render-backend abstraction** (native pyqtgraph *and* matplotlib *and*
embedded-web Plotly from one API), while remaining **100% offline** and handling
**out-of-core big data** via Datashader. The closest conceptual rival, HoloViews, proves
the "describe once, render anywhere" model is valuable — but HoloViews is web-first and
has **no native-Qt/OpenGL backend at all**. qtviz's wedge is precisely that gap:
desktop-native first. The risks are equally real: it competes against extremely mature,
popular incumbents on each individual axis; its value is an *abstraction* rather than new
rendering capability; the desktop-Qt audience is smaller than the web/dashboard mainstream;
and as a pre-release solo project it carries adoption and maintenance risk.

---

## What qtviz is (per its docs)

A declarative, native-Qt (PySide6) plotting library for **data-intensive desktop apps**.
You describe a plot once as an immutable, value-hashed `Element`, then render it through a
chosen backend; the same description drops into any PySide6 app as a plain `QWidget`.

- **Backends:** pyqtgraph (default, native, OpenGL-capable), matplotlib (static/vector
  export), webengine (Plotly in an embedded `QWebEngineView`; requires a real display).
- **Vocabulary:** 8 elements (Scatter, Curve, Bars, Histogram, Image, Heatmap, ErrorBars,
  Spread) + `RawFigure` passthrough; `Overlay` (`*`) / `Layout` (`+`) composition; typed
  events (`Range`/`Pick`/`Select`/`Hover`/`Tap`).
- **Data:** container-agnostic, lazy-first — dict/NumPy/pandas/Arrow eager, Dask/xarray/zarr
  out-of-core; channels bind to a column name, a lazy `Expression`, a callable, or an array.
- **Big data:** Datashader rasterization (`scale="datashader"|"auto"`) with viewport
  re-aggregation on zoom, out-of-core, backend-agnostic; hover a raster to read the
  aggregated value (`HoverEvent.value`).
- **Reactive:** S-style `signal`/`derived`/`effect`/`batch`; `View(Signal[Node])` re-renders
  on change (crossfilter without manual wiring).
- **Interop:** one-way `from_holoviews()` translates a HoloViews tree to native Elements
  (`RawFigure` fallback for the long tail); `DynamicMap` → reactive re-render;
  `from_hvplot()` one-liner.
- **Offline:** no network at render time, ever; the webengine backend bundles its JS from
  the installed packages rather than a CDN.

---

## The competitive landscape

Python visualization in 2025–2026 is usually framed in three buckets, none of which is
*desktop-native-first*:

1. **Interactive web-first** — Plotly/Dash, Bokeh, Vega-Altair, ECharts. Render in a
   browser; "desktop" means embedding HTML in a `QWebEngineView` (often plus a localhost
   server). This is the mainstream growth area.
2. **Static / publication** — Matplotlib (the foundation of the ecosystem), Seaborn,
   plotnine. Excellent vector export; weak interactivity/large-data.
3. **Dashboard runtimes** — Streamlit, Panel, Dash. Always server-backed, browser-rendered.

Separately, a **native/GPU desktop** cluster exists but is largely absent from mainstream
roundups: pyqtgraph, VisPy, the newer fastplotlib/pygfx (WGPU), napari (image viewer), silx,
DearPyGui (not Qt), and Qt's own charting (Qt Charts, deprecated since ~6.10 → Qt Graphs).

### The pivotal facts from research

- **HoloViews is the only widely-recognized "one declarative spec → multiple backends"
  library** (Bokeh/matplotlib/Plotly via a `Store` registry). But its three renderers are
  **all web/static targets** — there is **no Qt, OpenGL, or desktop-GUI backend** anywhere in
  its current docs or releases. Desktop use means a web view. *(holoviews.org)*
- **Every web-first library's "native desktop" is a `QWebEngineView`.** Offline
  self-containment is achievable but **opt-in**: Bokeh (`Resources(mode=INLINE)`) and Plotly
  (`include_plotlyjs=True`) can inline their JS; Altair/Streamlit/Dash are weaker (CDN assets
  and/or a mandatory server). qtviz's "offline, JS bundled locally" matches best-case
  Plotly/Bokeh and beats the rest.
- **Matplotlib in Qt is slow for live/large data.** Vendor and third-party figures put
  pyqtgraph at ~50–60 fps vs matplotlib ~5–15 fps for 10k-point live updates; VisPy renders
  5M-point 3D scatter at ~45 fps where matplotlib stalls near 1 fps. Matplotlib's genuine moat
  is **vector export** (PNG/SVG/PDF). This validates qtviz's core thesis: developers currently
  must *choose* between interactive speed (pyqtgraph) and publication export (matplotlib).
- **The native/GPU options are imperative, single-engine, and non-declarative.** pyqtgraph,
  VisPy, fastplotlib/pygfx, DearPyGui — all fast, none offer a declarative spec or a unified
  static-export story. silx is the lone partial analog (it can render 2D plots through *either*
  matplotlib or OpenGL widgets) but is narrow and synchrotron-focused.
- **Datashader is shared infrastructure, not a moat.** qtviz, the HoloViz stack, and
  (via images) Plotly/Bokeh all use it.

---

## Capability comparison

How qtviz stacks up on the axes that define its pitch. ("Native Qt" = renders as a real Qt
widget, not a browser view. "Multi-backend" = one API targeting multiple render engines.
"Big data" = out-of-core / Datashader-class scaling. Maturity is order-of-magnitude.)

| Library | Declarative API | Multi-backend | Native Qt widget | Offline | Big data (OOC) | Vector export | Maturity (≈ stars) |
|---|---|---|---|---|---|---|---|
| **qtviz** | **Yes** (immutable) | **Yes** (pyqtgraph + mpl + web) | **Yes** | **Yes, by design** | **Yes** (Datashader, OOC) | Yes (via mpl) | Pre-release, alpha (n/a) |
| pyqtgraph | No (imperative) | No (Qt/GL) | Yes | Yes | Partial (downsample only) | No | Mature (~4.3k) |
| matplotlib | No (imperative)¹ | No | Embeds (`FigureCanvasQTAgg`) | Yes | No | **Best-in-class** | Dominant (~21k) |
| HoloViews | **Yes** | **Yes** (bokeh/mpl/plotly) | No (web only) | Partial (bokeh inline) | Yes (Datashader) | Via mpl backend | Mature (~2.9k) |
| Plotly / Dash | Partial | No | No (QWebEngineView) | Opt-in (inline JS) | Via Datashader→image | Weak | Very popular (~18k) |
| Bokeh | No (glyph) | No | No (QWebEngineView) | Opt-in (INLINE) | Datashader / server | Weak | Popular (~20k) |
| Vega-Altair | **Yes** (grammar) | No | No (QWebEngineView) | Weak (CDN assets) | No (≈5k–100k row cap) | Weak | Popular (~10k) |
| VisPy / fastplotlib | No (imperative) | No (GL/WGPU) | Yes (+ others) | Yes | GPU-resident (in-mem) | No | Active (~1.5–3.6k) |
| LightningChart (commercial) | No | No | Yes (PyQt) | Yes | GPU/WebGL (millions) | Limited | Commercial/paid |

¹ Seaborn's objects interface and plotnine add a declarative grammar *on top of* matplotlib,
but remain single-backend and static.

The point of the table: **most rows are strong on one axis and absent on others. qtviz is the
only row that claims the full set** — declarative + multi-backend + native-Qt + offline +
out-of-core. silx and Qt Graphs each touch one extra axis; nothing else hits the combination.

---

## Strengths (the genuine differentiators)

1. **It fills a real white space.** "One immutable declarative description → native-Qt fast
   (pyqtgraph) + publication export (matplotlib) + web (Plotly), fully offline, big-data,
   desktop-first" has no direct competitor. HoloViews validates the multi-backend model; qtviz
   is the native-Qt analog HoloViews never built.
2. **It resolves a real either/or.** Developers embedding plots in PySide6 apps today choose
   between pyqtgraph (fast, imperative, no export) and matplotlib (export, slow, not native).
   qtviz lets the *same* `Element` be both — fast interaction during use, vector export for a
   report — by swapping a backend keyword.
3. **Offline is a first-class invariant, not a footnote.** For air-gapped/regulated/industrial
   desktop software, "no CDN, no server, no network at render time" is a hard requirement that
   the web-first stack only meets in opt-in best-case configurations.
4. **The big-data story is credible.** Out-of-core Datashader rasterization that re-aggregates
   to the viewport, *backend-agnostically*, plus a lazy Dask/xarray/zarr layer resolved off the
   GUI thread, is more than most native plotters offer (pyqtgraph only downsamples).
5. **Pragmatic interop, not lock-in.** The one-way HoloViews/hvPlot adapter and `RawFigure`
   passthrough mean existing HoloViews/Plotly/Bokeh work isn't thrown away — a smart adoption
   on-ramp rather than a rewrite demand.
6. **Engineering discipline is visible.** A written spec, a decision log, tiered tests, a
   backend/adapter conformance suite, and a documented offline guarantee are unusual for a 0.1
   and lower the "is this a toy?" risk.

---

## Weaknesses, risks, and the skeptic's case

1. **"Why not HoloViews + Panel (in a web view)?"** is the obvious objection. qtviz must keep
   justifying *native Qt* over *embedded web* — for many teams a `QWebEngineView` is "good
   enough," and the web ecosystem is far larger and better resourced.
2. **It adds an abstraction, not new rendering power.** pyqtgraph's speed and matplotlib's
   export already exist. The value is the unifying API — which lives or dies on whether the
   lowest-common-denominator `Element` can expose enough of each backend's capability.
   HoloViews is routinely criticized for leaky abstractions and backend-specific styling
   escape hatches; qtviz will face the same pressure as users demand per-backend control.
3. **It does not win on raw performance.** GPU-native engines (VisPy, fastplotlib/pygfx on
   WGPU, commercial LightningChart) will out-render it for millions of live points. qtviz
   should sell *declarative unification + offline + export*, not "fastest" — its pyqtgraph
   path is fast, but it is not a GPU-first engine.
4. **Smaller addressable audience.** The field's momentum is web/dashboard (Plotly, Streamlit,
   Dash). A desktop-Qt-only library targets scientific/engineering/instrumentation/industrial
   desktop apps — a real but narrower market, and one where pyqtgraph already has mindshare.
5. **Maturity and bus-factor.** Pre-release, not on PyPI, alpha, APIs may change, apparently
   single-maintainer. The webengine backend needs a real display (no headless rendering) and
   its large-payload binary transport is still pending. Several roadmap items its own docs flag
   as unbuilt — Parquet/DuckDB **data sources**, **axis transforms** (log/datetime), **legends
   on datashaded rasters**, **brush/selection on rasters** — are table stakes for some users.
6. **Unproven claims.** The test count and offline rigor are encouraging, but performance and
   robustness are self-reported; there is no independent benchmark or production track record
   yet.

---

## Who should care — and who shouldn't

**A good fit for:**
- Teams building **PySide6/PyQt desktop applications** that need embedded, interactive plots
  and currently juggle pyqtgraph *and* matplotlib.
- **Offline / air-gapped / regulated** environments (industrial, defense, clinical, finance)
  where browser/CDN/server-based stacks are awkward or disallowed.
- **Large-data desktop** workflows (millions+ points, lazy Dask/xarray sources) that want
  Datashader without standing up a Bokeh/Panel server.
- Existing **HoloViews/hvPlot** users who want their declarations to render as native Qt
  widgets.

**Probably not worth it for:**
- Web dashboards or notebook-first analysis → Plotly/Dash, Bokeh, Altair, HoloViz+Panel.
- Pure publication figures → matplotlib/seaborn/plotnine directly.
- Maximum-FPS GPU rendering of huge live point clouds → VisPy, fastplotlib/pygfx, or
  commercial LightningChart.
- Teams that can't accept pre-release/alpha risk today.

---

## Bottom line

qtviz is a **thoughtfully-engineered answer to a question the mainstream ecosystem hasn't
answered: a declarative, multi-backend, offline, big-data plotting library that is
*desktop-native first*.** Its strategy — clone HoloViews' proven "describe once" model, then
add the native-Qt backend HoloViews lacks, plus an offline guarantee and out-of-core
Datashader — is coherent and targets a genuine gap. Whether it becomes broadly valuable
depends on execution beyond `0.1`: shipping the still-missing fundamentals (data sources,
axis transforms, richer raster interaction), proving the declarative abstraction doesn't
become leaky under real per-backend demands, and earning trust as a maintained, published
project. As of this review it is a **strong, well-reasoned bet on an underserved niche** —
not yet a proven, drop-in production tool. For desktop-native, offline, large-data Qt apps it
is worth tracking closely and prototyping with; for web/dashboard or publication-only work,
the incumbents remain the better default.

---

## Sources

Competitor facts drawn from web research (mid-2026):

- HoloViews backends/renderers: holoviews.org/user_guide/Plots_and_Renderers.html ·
  holoviews.org/user_guide/Large_Data.html
- HoloViz stack: hvplot.holoviz.org · github.com/holoviz/panel · github.com/holoviz/datashader
- Bokeh offline (`INLINE`): docs.bokeh.org/en/latest/docs/reference/io.html
- Plotly offline (`include_plotlyjs`): plotly.com/python-api-reference/generated/plotly.io.write_html.html
- Vega-Altair large-data limits / VegaFusion: altair-viz.github.io/user_guide/large_datasets.html
- Streamlit-in-a-webview pattern: stefsmeets.nl/posts/streamlit-webview/
- Matplotlib Qt embedding: matplotlib.org/stable/api/backend_qt_api.html ·
  pythonguis.com/tutorials/pyside6-plotting-matplotlib/
- pyqtgraph vs matplotlib performance: pyqtgraph.com/is-pyqtgraph-better-than-matplotlib-for-live-plots/
- pyqtgraph / VisPy / napari / silx / DearPyGui / fastplotlib / pygfx: respective GitHub repos
  and docs (vispy.org, napari.org, github.com/silx-kit/silx, dearpygui.com,
  github.com/fastplotlib/fastplotlib, pygfx.org)
- Qt charting: doc.qt.io/qt-6/qtgraphs-index.html · doc.qt.io/qtforpython-6/PySide6/QtGraphs/
- Declarative-on-matplotlib: seaborn.pydata.org/whatsnew/v0.12.0.html · plotnine.org
- Commercial GPU comparison: lightningchart.com/python-charts/
- Field framing / roundups: reflex.dev/blog/2025-10-27-top-10-data-visualization-libraries/ ·
  index.dev/blog/python-data-visualization-libraries

qtviz capabilities are from the project's own `README.md`, `design/` (spec, roadmap,
capabilities-gaps, decision log), `CHANGELOG.md`, and `examples/` — self-reported and not
independently verified for this review.
