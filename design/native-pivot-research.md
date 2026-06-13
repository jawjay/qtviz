# Native Qt pivot — research & decision

> Companion to `roadmap.md`. The roadmap is the *what / when*; this doc is
> the *why* behind the Option A vs B decision and the framing shift from
> "Qt + JS" to "Qt + JS + native (pyqtgraph, matplotlib)".

## 1. What changed

Previous framing — `qtwebplot` wraps Qt WebEngine; visualizations are
JavaScript (Plotly, Bokeh, HoloViews-via-Bokeh, future deck.gl). Native
Qt drawing was not in scope.

New framing — the framework is *Qt plotting*. Backends can be:

1. **`pyqtgraph`** — native, OpenGL-backed, low-latency. Real-time and
   interactive use cases.
2. **`matplotlib`** — native via `FigureCanvasQTAgg`. Publication
   quality, broad ecosystem.
3. **`webengine`** — the current `WebBridgeView` path. Plotly / Bokeh /
   any JS library. Retained as the "JS backend".

The composition / declarative layer sits above all three.

## 2. The HoloViews question

We need a declarative composition layer ("Element × backend × composition
× streams"). HoloViews has spent ~10 years building this. The choice:

- **Option A** — extend HoloViews. Add a pyqtgraph backend; improve the
  matplotlib backend's Qt story.
- **Option B** — build a Qt-native equivalent.

### 2a. HoloViews extension surface

HoloViews backends register via `Store.register({Element: Plot}, name)`.
Each backend ships:

- A `Renderer` subclass — entry point that returns embeddable output
  (HTML, PNG, Figure, …).
- A base `Plot` class plus an `ElementPlot` subclass *per element type*
  the backend supports. The bokeh backend has ~55 such subclasses
  (Scatter, Curve, Bars, BoxWhisker, Spread, Area, Histogram, Image,
  RGB, Raster, QuadMesh, Heatmap, HexTiles, Spikes, Polygons, Path,
  Contours, Graph, Sankey, Chord, ErrorBars, …).
- Composition: `OverlayPlot`, `LayoutPlot`, `GridPlot` (these stay
  somewhat backend-aware because they manage shared axes / linked
  brushes via the backend's primitives).
- Stream handlers wiring `RangeXY`, `BoundsXY`, `Tap`, `Selection1D`,
  etc. to the backend's native events.

The HoloViews `MPLRenderer` already returns matplotlib `Figure` /
`MPLPlot` objects, not HTML bytes. Wrapping in `FigureCanvasQTAgg` is
straightforward. The bokeh and plotly Renderers return HTML / `Bokeh
Document` objects; the assumption everywhere is "embed in a notebook or
server."

### 2b. What "improve matplotlib in HoloViews" actually means

The matplotlib HoloViews backend exists and is mature in element
coverage. What's weak in a Qt-native context is:

1. **Interactivity.** HoloViews streams on the matplotlib backend rely on
   matplotlib's event system, which is slow vs Qt's native event loop
   and lacks crisp idle-throttling.
2. **Qt integration.** No first-class translation of mpl events →
   `QObject` signals; no shared theme; no Qt event-loop awareness for
   stream debouncing.
3. **Performance.** mpl redraws are full-canvas; blitting is possible
   but HoloViews doesn't drive it.

"Improving" this is mostly *wrapping* work, not patches to HoloViews
itself: a `qtviz.mpl.wrap(hv_obj)` that returns a `FigureCanvasQTAgg`
with a Qt event bridge and theme awareness. Maybe 1 week. Not a
multi-month upstream campaign.

### 2c. Option A — full extension

To add `pyqtgraph` as a HoloViews backend properly:

| Surface                                | MVP scope            | Feature-parity scope |
|----------------------------------------|----------------------|----------------------|
| `PyQtGraphRenderer`                    | 1 class              | 1 class              |
| `ElementPlot` subclasses               | 10–12 (the staples)  | 50+ (parity w/ bokeh)|
| `OverlayPlot` / `LayoutPlot`           | 2                    | 2                    |
| Stream handlers                        | 4–5 streams          | ~15 streams          |
| `Store.register` wiring                | 1                    | 1                    |
| Qt event bridge (signals/slots ↔ streams) | layer            | layer                |

Estimate: **3–5 months MVP, 12–18 months for parity.**

#### What we'd inherit (the wins)

- The Element vocabulary (~80 types, several years of design).
- Composition operators (`*`, `+`, `GridSpace`, `HoloMap`, `DynamicMap`).
- `.opts()` customization API.
- Streams + linked selections.
- `hvplot.scatter(...)` returning *our* widget transparently — pandas,
  Dask, xarray users pick us up for free.

#### What we'd pay for (the costs)

- **Renderer architecture mismatch.** HoloViews Renderers return
  embed-bytes (HTML, PNG, bokeh `Document`). Returning a `QWidget`
  works but is unprecedented inside HoloViews. Two options:
   - **Out-of-tree**: ship `holoviews-pyqtgraph` as a separate
     installable package (like `hvplot`). We own it; no upstream
     coordination. This is the realistic path.
   - **Upstream**: PR the architecture change into HoloViews itself.
     Slow, requires HoloViz buy-in, version-coupling forever.
- **Param ↔ Qt signals impedance mismatch.** HoloViews is Param-based;
  Qt is signals/slots. A bridge layer is needed; it works but adds a
  layer of indirection that complicates debugging.
- **Element coverage forever lags Bokeh.** We will never have all 55
  ElementPlots. Users coming from `.hvplot()` will hit "not supported on
  this backend" errors.
- **API drift.** HoloViews releases regularly; backend code tracks
  internal APIs that are not strictly stable.
- **Composition awkwardness for Qt-only features.** HoloViews Layouts
  produce a grid figure; they don't model `QSplitter`, `QDockWidget`,
  `QTabWidget` resizing, side-by-side comparison panes, or inspector
  docks — all of which a Qt-native plotting library should produce.

### 2d. Option B — Qt-native, HoloViews-equivalent

Build our own `Element / Backend / Composition / Streams` layer, Qt
first.

| Surface                  | MVP scope                                  |
|--------------------------|---------------------------------------------|
| Element types            | 6–10 (Scatter, Curve, Bars, Image, Heatmap, Histogram, Spread, ErrorBars, Polygons, Path) |
| Backends                 | 3 (pyqtgraph, matplotlib, webengine)        |
| Render methods           | ~24 (8 elements × 3 backends)               |
| Composition operators    | `Overlay`, `Layout` + Qt-native: `Splitter`, `Tabs`, `Dock` |
| Stream / event protocol  | 5 typed events: range, pick, select, hover, tap |
| Theme protocol           | Already done (`qtviz.Theme`)                |
| Reactive runtime         | Signal / derived / effect (carryover)       |

Estimate: **4–6 months MVP**, similar wall-clock to Option A MVP, but
shipping a complete product rather than a fragmented backend.

#### Advantages

- Clean architecture: signals/slots end-to-end, QPainter / OpenGL
  native, Qt event-loop aware.
- Composition can model Qt-only ideas: dockable inspector, splitter
  layouts, tabbed canvases, side-by-side compare. HoloViews can't.
- No upstream coordination; we own API stability.
- Element coverage is "what we ship" — we're not benchmarked against
  Bokeh's 55-class backend.

#### Disadvantages

- Reinvents an Element vocabulary HoloViews users already know.
- Users must learn a new API.
- No instant `hvplot` integration.
- We have to spec composition semantics ourselves (overlay rules,
  shared axes, theme cascading).

### 2e. Option C — recommendation: Option B + HoloViews adapter

Build Option B as the core. On top, ship a thin one-way adapter:

```python
import qtviz, holoviews as hv

hv_obj = hv.Scatter(df, "x", "y") * hv.Curve(df, "x", "y_smooth")
view = qtviz.from_holoviews(hv_obj)              # returns QWidget
```

The adapter walks the HoloViews tree (Element / Overlay / Layout /
HoloMap), translates each node into the corresponding `qtviz` Element,
and renders. Translation table covers the subset of HoloViews Elements
we have native equivalents for; unsupported elements raise with a clear
"not supported in qtviz adapter — use `hv.render` for full Bokeh
output" message.

This is `hvplot`-style: thin shim, no upstream HoloViews work, no
rebuilt plot classes. HoloViews users get Qt-native rendering for the
subset we support. Coverage grows when we add Elements to qtviz, not
when we PR HoloViews.

The matplotlib HoloViews wrapper is the same: `qtviz.wrap_mpl_hv(hv_obj)`
returns `FigureCanvasQTAgg` with theme + event bridge. ~1 week.

### 2f. Decision: **Option B (Qt-native) + Option C adapter**

Reasons, in order:

1. **Architecture fit.** HoloViews' Renderer hierarchy assumes
   embed-bytes; Qt wants `QWidget`. Forcing a third paradigm onto
   HoloViews is more work than building Qt-first.
2. **Composition fit.** Qt-only composition (splitters, docks, tabs) is
   beyond what HoloViews models. Option B exposes them naturally.
3. **Element coverage realism.** Option A would ship perpetually
   half-covered relative to bokeh. Option B ships *the elements we
   ship* — no implied comparison.
4. **Upstream coupling.** Option A binds our roadmap to HoloViews
   release cadence. Option B does not.
5. **Adapter retains the wins.** HoloViews users still get a one-line
   path to our renderer via `qtviz.from_holoviews()`; pandas/xarray
   users get the `hvplot` chain via a small extension shim.

The cost we accept: users have to learn the qtviz API. The mitigation:
the API is small (Element + composition operators + Theme) and the
adapter exists for the HoloViews-fluent crowd.

## 3. Backend roles

| Backend         | Strength                              | Use it for                                |
|-----------------|---------------------------------------|--------------------------------------------|
| `pyqtgraph`     | Real-time, OpenGL, low-latency, native | Interactive dashboards, streaming, scope-style displays |
| `matplotlib`    | Publication quality, broad ecosystem  | Reports, static figures, "I know mpl"      |
| `webengine`     | Plotly / Bokeh / any JS lib            | Rich web visualizations, migration from notebooks |

Backend chosen by user (`view.backend = "pyqtgraph"`) or auto-selected
("interactive + n > 100k → pyqtgraph; static + report → matplotlib;
plotly-specific feature → webengine").

`qtwebplot` is *not* deprecated. It is the `webengine` backend. The
existing `WebBridgeView`, layouts, theming, and linking move under
`qtviz.backend.webengine` largely intact — they remain the "JS path"
and the Studio still benefits from them.

## 4. What this means for the Datashader/GPU story

The previous roadmap committed to `deck.gl` + Datashader for 100M–1B
points. Under the native pivot:

- **pyqtgraph** handles 1–10M points natively at 30+ FPS — it's already
  GPU-accelerated for many primitives (`pg.opengl`, `ScatterPlotItem`
  with hundreds of thousands of points).
- **Datashader → pyqtgraph image item** is straightforward — render the
  rasterized image into a `pg.ImageItem`, hook up the ViewBox range to
  trigger re-aggregation. No browser involved.
- **deck.gl** stays in scope only via the `webengine` backend, and only
  if a user actually needs WebGL for some specific scene (e.g.,
  geographic / map overlays). Most "big data scatter" needs are met by
  pyqtgraph + Datashader natively.

This is a strict simplification: we drop one dependency (deck.gl as a
*core* commitment) and lean on Python-native libraries we already
trust.

## 5. Pyqtgraph capabilities used

| Feature                        | API                                              |
|--------------------------------|--------------------------------------------------|
| Composition                    | `GraphicsLayoutWidget.addPlot(row, col)`         |
| Linked axes                    | `ViewBox.setXLink(other)`, `setYLink`            |
| Range events                   | `ViewBox.sigRangeChanged`                        |
| Picks                          | `ScatterPlotItem.sigClicked(points)`             |
| Brush                          | `LinearRegionItem`, `PolyLineROI`                |
| OpenGL                         | `pyqtgraph.opengl` for 3D; `useOpenGL=True` for 2D |
| Image                          | `ImageItem.setImage(numpy)`                      |
| Real-time                      | Designed for it — used in oscilloscope / DAQ work|

Every interactive feature we'd need from a JS library has a pyqtgraph
equivalent. The gap is *composition / declarative API*, which is what
qtviz provides.

## 6. Matplotlib in Qt

Standard wiring:

```python
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
canvas = FigureCanvasQTAgg(fig)
```

Mature, supported, slow. Event integration via mpl's event system; we'd
add a thin translator: `mpl.event → qtviz typed signal`.

For `hvplot` / HoloViews users who insist on matplotlib output (common
in scientific Python), wrapping `holoviews.render(obj, backend="mpl")`
in `FigureCanvasQTAgg` gets them in our composition system in 1 LOC.

## 7. Project naming

The project is no longer "Qt + web plotting"; it's "Qt plotting".

Suggested rename: **`qtviz`** (working name).

Alternatives:

- `qtplots` — too generic, may conflict
- `qtviz` — short, memorable, available on PyPI as of last check
- `qtcanvas` — overloaded with Qt's own QCanvas history
- `qtgraph` — collides with pyqtgraph
- keep `qtwebplot` — misleading now; the `web` is one of three backends

Recommendation: **rename to `qtviz`**. Keep `qtwebplot` as the package
name for the `webengine` backend subpackage to preserve the import
history.

## 8. Decision summary

| Question                                     | Answer                                     |
|----------------------------------------------|---------------------------------------------|
| Option A (extend HoloViews) or B (native)?   | **B + adapter (Option C)**                 |
| Pyqtgraph as core backend?                   | **Yes — primary interactive backend**       |
| Matplotlib as core backend?                  | **Yes — secondary, via `FigureCanvasQTAgg`**|
| Webengine path (existing qtwebplot)?          | **Yes — retained as third backend**        |
| HoloViews integration?                        | **One-way adapter `qtviz.from_holoviews()`**|
| deck.gl / WebGL?                              | **Demoted — only via webengine backend**   |
| Datashader?                                   | **Native via `pg.ImageItem`**              |
| Project rename?                               | **`qtwebplot` → `qtviz` (working name)**   |
| Studio still in scope?                        | **Yes, but after library 0.1**             |

## 9. Open questions before Phase 0

1. **Project name**. `qtviz` working — confirm or pick another. Affects
   PyPI / GitHub reservations.
2. **Element vocabulary cut**. Which 6–10 elements ship in Phase 1?
   Proposed: Scatter, Curve, Image, Heatmap, Bars, Histogram, ErrorBars,
   Spread.
3. **Auto-backend policy**. Hardcoded thresholds? `Element` hint? User
   choice only? Recommend: user choice via `Element(..., backend=...)`
   with sane default per element.
4. **HoloViews adapter scope**. Which HoloViews Elements does it
   translate? Same as our native list?
5. **Datashader integration depth**. In Phase 4 or Phase 6? Recommend
   Phase 4 — pyqtgraph backend + Datashader image is more useful than
   adding a 7th element.
6. **Studio deferral**. Confirm Studio moves to post-1.0.

## 10. What this doc supersedes

- The "deck.gl as primary GPU backend" decision in the prior roadmap.
  Demoted.
- The "Datashader via JS image transport" path. Replaced by native
  `pg.ImageItem` integration.
- The "JS-only visualizations" framing of the entire project. Replaced
  by tri-backend (`pyqtgraph` / `matplotlib` / `webengine`).

The `dask-datashader-research.md` doc remains valid — its conclusion
("integrate, don't compete") applies to either pivot, and the Dask
data-source work in Phase 5 carries over unchanged.
