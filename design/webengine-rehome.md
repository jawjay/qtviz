# Design — rehoming the WebEngine bridge as the `webengine` backend

> A plan, from a read of `src/qtwebplot/`, for bringing the legacy Qt↔JS bridge
> (Plotly / Bokeh / HoloViews in a `QWebEngineView`) inside qtviz as a registered
> `webengine` backend behind the native Backend protocol. Companions: `spec.md`
> §2 (Backend protocol), `roadmap.md` Phase 5, `architecture.md` (the legacy
> bridge as-is). Output of the investigation requested before the HoloViews
> adapter; **no code yet** — this is the design to review first.

## 1. What we're deciding

The legacy package renders *web* plotting libraries; qtviz renders *native* Qt.
The goal is **"same Element, more backends"**: `View(Scatter(...),
backend="webengine")` draws through Plotly-in-a-webview, and a user's existing
Plotly/Bokeh/HoloViews figure can be hosted too — all behind the same `Backend`
contract the pyqtgraph/matplotlib backends already satisfy. This doc maps the
seams and sequences the move.

## 2. As-is: the legacy bridge (two layers)

```
PlotView(WebBridgeView)                     ← convenience: bind a PlotBackend, render
  └─ WebBridgeView(QWidget)                 ← the primitive (plotting-agnostic)
        ├─ QWebEngineView + _BridgePage     ← console-log piping
        ├─ Bridge(QObject) over QWebChannel ← JS↔Py envelope: (name, payload)
        ├─ send()/received signal           ← bidirectional named messages
        ├─ command queue until `ready`      ← survives async page load
        ├─ per-name trailing throttle       ← e.g. hover/relayout
        └─ CORE_JS + qwebchannel.js inject  ← window.qtwebplot.{send,on,onReady}
PlotBackend (Protocol)                      ← to_html() · js_runtime() · on_attach(view)
  ├─ PlotlyBackend   to_html via plotly.io; events attached in runtime JS
  │                  (plotly_hover/click/selected/relayout); verbs react/restyle/extend
  ├─ BokehBackend    file_html + CustomJS instrumentation (Tap/Select/RangesUpdate);
  │                  verbs patch/stream; version-tolerant model lookup
  └─ HoloViewsBackend  hv.renderer("bokeh").get_plot(obj).state → a Bokeh model,
                       then delegates entirely to BokehBackend
layouts.py   PlotGrid/Tabs/Splitter         ← own composition + lazy tabs
_linking.py  link(source, event, targets)   ← cross-view forwarding by message name
theme.py     Theme(bg/fg/grid/palette/font) ← parallel to qtviz core Theme
```

Key properties: `WebBridgeView` is solid and plotting-agnostic; the page load is
**async** but the `send()` command queue + `ready` signal already bridge that gap;
events are library-specific dataclasses + Qt signals routed by message name.

## 3. The crux — two protocols

| | qtviz `Backend` (`core/backend.py`) | qtwebplot `PlotBackend` (`backend.py`) |
|---|---|---|
| Unit | a **Node** (Element/Overlay/Layout) | a **figure** (Plotly/Bokeh object) |
| Entry | `render(node, *, theme, parent) → RenderHandle` | `to_html()` + `js_runtime()`, attached to a view |
| Selection | one backend per node, **negotiated** | user constructs the PlotBackend directly |
| Events | typed `Event`s on an `EventBus` | library dataclasses on per-backend Qt signals |
| Lifecycle | synchronous: handle is ready on return | async: HTML loads, JS handshake, then `ready` |

The rehome is mostly **wrapping** the second under the first: one qtviz
`WebEngineBackend` whose renderers turn Elements into a figure, host it in a
`WebBridgeView`, and translate library events into qtviz `Event`s.

## 4. Target design

```
View(node, backend="webengine")
  → WebEngineBackend.render(node, theme)               # implements qtviz Backend
       node is Overlay/Element → Element→figure renderers build ONE Plotly figure
       node is a RawFigure(passthrough)  → use the user's Plotly/Bokeh/HV object
  → wrap in a PlotBackend (default PlotlyBackend) + WebBridgeView
  → load_html(); WebBridgeView.received → event translator → EventBus typed events
  → return WebEngineRenderHandle(widget=WebBridgeView, event_bus=…)
```

**Backend ↔ legacy mapping:**

| qtviz `Backend`/`RenderHandle` member | webengine implementation |
|---|---|
| `render(node, theme, parent)` | Element-renderers → Plotly figure (or raw figure) → `PlotBackend` → `WebBridgeView.load_html` |
| `RenderHandle.widget` | the `WebBridgeView` (already a `QWidget`) |
| `RenderHandle.event_bus` | new `EventBus`; subscribe `view.received` → translate → emit typed events |
| `capture_state`/`restore_state` (`ViewState`) | Plotly `relayout` to set/read axis ranges; selection ↔ `SelectEvent` indices |
| `update(new_root)` | rebuild figure → `react()` (fast) or `load_html()` (full); stream/extend verbs for live data |
| `export(fmt, path)` | `to_png` (raster, native); svg/pdf via Plotly+kaleido (optional) |
| `capabilities` | dims {2,3}, opengl (scattergl), picking native, **brush native** (box/lasso), range_events, streaming, animation, exports {png(+svg/pdf)}, `gui_only` |
| `can_host(kind)` | `False` — no native mixed panes; qtviz `LayoutHost` composes per-pane `WebBridgeView`s |
| `supports(element_type)` | the Element→figure `RendererRegistry`, mirroring pyqtgraph/mpl |

**Event translation** (the boundary that makes "one Element, one meaning" hold):
`view.received("plotly.click", …)` → `PickEvent`; `plotly.selected` →
`SelectEvent` (trace/point indices map straight to row indices); `plotly.relayout`
→ `RangeEvent`; `plotly.hover` → `HoverEvent`. The existing per-library event
dataclasses become an internal detail; the *public* stream is qtviz typed events,
so a webengine pane is indistinguishable to `View.on(...)`.

**Async render fits without changing `View`.** `render()` returns a
`WebEngineRenderHandle` immediately; the `WebBridgeView` is blank until
`loadFinished`/`ready`, and its **command queue already buffers** any `send()`
(restore_state, theme, data) issued before then. Events simply start flowing after
`ready`. (Contrast the *data* async path, which is keyed on `node_is_lazy`; this is
*backend* async and is self-contained in the handle.)

**Composition & linking are superseded, not rehomed.** A webengine `Overlay`
becomes multiple traces in one figure; a `Layout` is composed by qtviz's existing
`LayoutHost` placing each pane's `WebBridgeView` in a `QSplitter`/`QTabWidget`, with
a `CompositeRenderHandle` merging EventBuses. So `layouts.py` and `_linking.py` are
**replaced** by qtviz's Layout + EventBus — cross-pane brushing rides the merged
bus, not message-name links.

## 5. Reuse / adapt / build / drop

| Disposition | Pieces |
|---|---|
| **Reuse wholesale** (lift into `backends/webengine/_bridge/`) | `core/web_bridge_view.py`, `core/bridge.py`, `core/_runtime.py` (CORE_JS), `core/_inject.py`, the per-library `_runtime.py` (event JS + mutation verbs) |
| **Adapt** | `ext/*/backend.py` → internal "figure hosts" driven by qtviz Element renderers + qtviz `Theme`; reuse their event JS but retarget payloads to qtviz `Event`s |
| **Build new** | `WebEngineBackend` (implements `Backend`), `WebEngineRenderHandle`, Element→Plotly renderers (the 8 types), a `RawFigure` passthrough element/escape-hatch, the event-translation layer, capability record |
| **Drop / supersede** | `view.py` (PlotView), `layouts.py`, `_linking.py`, `theme.py` → qtviz `View` / `Layout` / `LayoutHost` / `EventBus` / core `Theme` |

## 6. The HoloViews relationship (why this comes first)

Two HoloViews paths, complementary:

- **webengine (full fidelity):** the legacy `HoloViewsBackend` renders *any* hv
  object via `hv.renderer("bokeh").get_plot(obj).state` → Bokeh-in-browser. Nothing
  is lost; nothing is native.
- **native adapter (Phase 3, planned):** `from_holoviews(obj)` translates the
  common hv elements → native qtviz Elements (Scatter/Curve/…) for pyqtgraph/mpl —
  fast and interactive, but only the subset qtviz models.

**Division of labor:** `from_holoviews()` translates what it can natively and
**falls back to a webengine `RawFigure`** for the long tail (Sankey, Chord, custom
hv). That fallback target must exist first — hence rehoming webengine *before*
building the native adapter. It also lets the adapter be incremental: ship the
common elements native, everything else still renders.

## 7. Open questions (new discussion items)

- **[D24] Default Element renderer for webengine — Plotly vs Bokeh.** Recommend
  **Plotly**: declarative JSON traces, native box/lasso select, WebGL (`scattergl`),
  3D, and static export via kaleido. Bokeh stays available as a figure host.
- **[D25] Async render contract.** Recommend returning the handle immediately and
  leaning on the existing command queue + `ready` (no `View` change). Decide whether
  to surface a "loading" placeholder for parity with the data path.
- **[D26] Raw-figure passthrough.** A first-class `RawFigure`/`WebFigure` element
  (negotiates only to webengine) vs. a backend-only escape hatch. Affects
  negotiation (only one backend `supports()` it) and `from_holoviews` fallback.
- **[D27] Event/selection fidelity.** Confirm the library→typed-event map and that
  Plotly selection point indices map cleanly to `SelectEvent` row indices across
  multi-trace figures.
- **[D28] `from_holoviews` fallback wiring** (depends on D26) — when/how the native
  adapter defers to webengine.
- **[D29] Transport.** JSON (current) is fine for moderate payloads; Arrow IPC for
  big data is a later optimization (roadmap Phase 5), gated on a measured need.
- **[D30] Packaging & physical move.** `webengine` extra = PySide6-WebEngine +
  per-library sub-extras (plotly/bokeh/holoviews). Move `src/qtwebplot/` under
  `src/qtviz/backends/webengine/`; keep a `qtwebplot` import shim with a deprecation
  warning (roadmap Phase 0/6).

## 8. Phased plan

> **Status (W0 ✅ landed).** `src/qtwebplot/` moved wholesale to
> `src/qtviz/backends/webengine/`; internal imports rewritten; a `sys.modules`
> redirect shim at `src/qtwebplot/` re-exports from the new location and warns
> once (`DeprecationWarning`). The WebEngine GUI tests are skip-gated under the
> offscreen platform (`QTVIZ_WEBENGINE_GUI=1` forces them). Suite green: 245
> passed, 11 skipped. **As-built deviation:** kept the inner `core/` + `ext/`
> module names (faithful relocation, smallest diff) — the §5 `_bridge/` rename is
> deferred to W1 when `WebEngineBackend` is built on top. Pre-existing ruff debt
> in the legacy code travelled with it untouched (it's superseded in W2–W4).
>
> **Status (W1 ✅ landed).** `WebEngineBackend` + `WebEngineRenderHandle`
> (`render.py`) registered as `webengine`: Scatter → Plotly figure (`_figure.py`,
> pure), bridge `received` → typed events (`_translate.py`, the D27 map), shadow
> axis-range state so `capture_state` stays synchronous, restore via queued
> `relayout`. Capabilities: dims {2,3}, opengl, native pick/brush, range/stream,
> animation, **exports `{}`** (png/svg/pdf need a rendered page or kaleido —
> deferred to W2 to stay honest). **Testing split (per the offscreen segfault):**
> the figure builder + event map are proven headless (`test_webengine_figure.py`,
> 11 tier-1 tests); the live render/event path is display-gated
> (`test_webengine_render.py`) and the full backend-conformance run is skipped
> offscreen via a general `requires_display` flag — both forcible with
> `QTVIZ_WEBENGINE_GUI=1`. The offscreen suite constructs no `QWebEngineView`, so
> it stays clean (256 passed, 20 skipped). **As-built:** reused the legacy
> `PlotView` as the internal host widget; the `core/` → `_bridge/` rename is
> still deferred (cosmetic, no functional need yet).
>
> **Status (W2 ✅ landed).** Element→Plotly renderers for all 8 types (`_figure.py`,
> each builder returns a *list* of traces so Spread's two-trace band keeps the
> trace→source-id table 1:1); every builder's output is validated to coerce
> through `plotly.io` (valid Plotly). Theme→layout translation; png export via
> `QWebEngineView.grab` (svg/pdf would need kaleido — later), `exports={"png"}`.
> **The real proof:** forced with `QTVIZ_WEBENGINE_GUI=1` the backend-conformance
> suite is **green for webengine — 36 passed** (all 8 elements render/dispose,
> state round-trips, png writes, subscriptions). The forced *offscreen* run still
> exits 139 at QApplication teardown (the known PySide6 WebEngine segfault, after
> the summary), so webengine stays gated out of the default suite by
> `requires_display`; the default suite is clean (259 passed, 21 skipped). New
> headless figure tests cover all 8 builders. Still deferred: `core/`→`_bridge/`
> rename; multi-trace selection routing (D27); svg/pdf export.

| Stage | Deliverable | Gate |
|---|---|---|
| **W0** ✅ | Physical move: whole `qtwebplot` package → `backends/webengine/`; redirect import shim; GUI tests skip-gated | existing bridge tests pass on new paths ✅ |
| **W1** ✅ | `WebEngineBackend` + `WebEngineRenderHandle`; render one `Scatter` via Plotly; register; declare capabilities; range + pick events | headless: figure+event map green; live draw/events display-gated (offscreen segfault) |
| **W2** ✅ | Element→Plotly renderers for the 8 types; theme translation; `capture/restore_state`; png export | backend-conformance green for webengine (forced: 36 passed); default-gated by the teardown segfault |
| **W3a** ✅ | `RawFigure` passthrough (host an existing Plotly/Bokeh/HV figure — all three *render*); Plotly typed events; **per-element `SelectEvent` routing** (D27); Plotly brush→`SelectEvent` | a raw figure of each lib renders; a Plotly raw figure + native Overlay emit per-element typed events |
| **W3b** ✅ | Bokeh event-translation map (`bokeh.tap`/`selection`/`ranges_update` → typed events) | a raw HoloViews/Bokeh object's brush emits typed events |
| **W4** ✅ | Mixed-backend `LayoutHost` panes (pyqtgraph + webengine), merged EventBus; drop legacy layouts/linking | a grid with a native pane beside a webengine pane shares one event stream |
| **W5.1a** (Phase 5) ✅ | Cheap win — `_figure.build` keeps numpy + `PlotlyBackend` coerces to `go.Figure`, so Plotly's base64 typed-array encoder engages | 1M pts: 757→180 ms, 38.5→27.0 MB; benchmark guards base64 |
| **W5.1b** (Phase 5) | If needed — explicit data-by-reference split + base64 Arrow over the existing channel | beats W5.1a for the multi-MB tail |
| **W5.2** (Phase 5) | Scale — swap the data blob to a binary `fetch` over a custom `qtviz` URL-scheme handler | <100 ms for a representative ~100 MB payload |

> **Status (W3a ✅ landed).** `qv.RawFigure(figure, kind=None)` (`elements/raw_figure.py`)
> — a first-class, standalone passthrough element that auto-detects the library
> (override with `kind=`) and negotiates only to webengine (D31). `WebEngineBackend`
> branches on it and hosts via `PlotlyBackend`/`BokehBackend`/`HoloViewsBackend`; an
> Overlay containing a `RawFigure` raises `IncompatibleOverlayError`. **D27 done:**
> `translate()` now returns a list and a `plotly.selection` emits **one `SelectEvent`
> per source element** (grouped by trace→source-id, matching native pyqtgraph); a raw
> figure emits one under its own id. Plotly raw figures bridge typed events; bokeh/hv
> raw figures render but get events in **W3b**. `resolve_node` hardened to pass
> data-less elements through. Headless tests cover detection/negotiation/overlay-reject
> + multi-trace selection; live raw render is display-gated. Suite: 269 passed, 22
> skipped (forced: 57 passed). Example 18 hosts a Plotly 3-D surface.

> **Status (W3b ✅ landed).** Bokeh event-translation map in `_translate.py`:
> `translate()` dispatches by message prefix (`plotly.*` vs `bokeh.*`); a
> Bokeh/HoloViews `RawFigure` now emits `bokeh.tap`→`TapEvent`,
> `bokeh.selection`→`SelectEvent` (bounds from the SelectionGeometry — row indices
> would need a data-source read, deferred), `bokeh.ranges_update`→`RangeEvent`
> (shadow-merged like Plotly relayout, via the handle's shared `_merge_range`).
> `bokeh.double_tap` has no qtviz equivalent. HoloViews inherits this for free (it
> renders through Bokeh and delegates the bridge plumbing). Verified end-to-end on
> a Bokeh figure and a HoloViews figure. Headless tests cover the bokeh map +
> `parse_bokeh_ranges`; the live bokeh raw render is display-gated. Suite: 274
> passed, 23 skipped (forced: 63 passed). Example 19 hosts a HoloViews scatter.
> **The original W3 gate is fully met.**
>
> **Status (W4 ✅ landed).** Mixed native + webengine panes compose through the
> existing M5 `LayoutHost`/`CompositeRenderHandle` with **zero new code** — the
> infra is backend-generic and the `WebEngineRenderHandle` satisfies the contract.
> `qv.View(qv.Layout([Scatter, RawFigure]))` (backend="auto") yields a composite
> whose `pyqtgraph` and `webengine` panes share one merged `EventBus`, so a single
> `View.on(...)` hears both (test + example 20). **Legacy composition retired
> (clean break, per user):** deleted `layouts.py` (PlotGrid/PlotTabs/PlotSplitter),
> `_linking.py`, the legacy `test_layouts_gui.py`, and the four legacy examples that
> used them; `qv.Layout` is now the one composition path. `view.py` (PlotView)
> stays — still the webengine host widget. **Known flake:** importing `qtviz` loads
> WebEngine into every test process (the backend registers eagerly), and offscreen
> Chromium occasionally segfaults mid-run (~1/5); the tests themselves pass — a
> process-level race, the same instability that gates the webengine tests.

After W3, the native HoloViews adapter (Phase 3) can be built against a real
fallback. W4 retires the legacy composition layer. **W5 (Arrow IPC transport) has
a dedicated design pass in [`webengine-arrow-transport.md`](webengine-arrow-transport.md)**
— format (Arrow IPC), transport (base64 → custom URL-scheme handler), the
figure-splitting it requires, and a benchmark-first plan.

## 9. Risks

- **WebEngine availability** — heavyweight dep, flaky in headless CI (the current
  `tests/test_layouts_gui.py` already times out offscreen). Mitigation: gate behind
  the extra; mark Tier-2 webengine tests `skip` when WebEngine/Chromium isn't usable.
- **Async timing in tests** — assert on the `ready` signal, not on a sleep
  (the legacy suite's pattern).
- **Library/event-API drift** (Plotly/Bokeh) — the legacy code already carries
  version-tolerant model lookup; keep that, pin tested ranges.
- **Two figure libraries** double the surface — keep Bokeh as a host only; make
  Plotly the one Element-renderer path to start.
