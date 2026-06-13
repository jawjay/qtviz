# qtwebplot — architecture

## What this is

A PySide6 widget that hosts arbitrary JS visualizations inside a Qt
application, with a bidirectional Python ↔ JS message bridge. Plotting
library bindings (Plotly, Bokeh, HoloViews) sit on top of this primitive as
opt-in extensions.

## Design principle

The core knows about **web pages and messages**, nothing more.

Anything chart-shaped — figures, traces, hovers, restyles — lives one layer up
in a library-specific module. This keeps the core usable for any JS content
(custom D3, three.js, deck.gl, Cesium, static dashboards) and prevents one
library's vocabulary from leaking into the public API.

## Three layers

```
┌──────────────────────────────────────────────────────────────┐
│  qtwebplot.ext.plotly  /  .bokeh  /  .holoviews  /  ...       │
│  Library-specific verbs, typed events, capability flags.      │
│  Each ext module brings its own optional dependency.          │
├──────────────────────────────────────────────────────────────┤
│  qtwebplot             (convenience layer)                    │
│  PlotView (WebBridgeView + backend composition).              │
│  PlotBackend Protocol — minimal: to_html + js_runtime.        │
├──────────────────────────────────────────────────────────────┤
│  qtwebplot.core        (primitive layer, no viz assumptions)  │
│  WebBridgeView, Bridge, JS bootstrap, HTML injection.         │
└──────────────────────────────────────────────────────────────┘
```

Each layer is usable directly. A consumer who needs a generic Qt-JS bridge
widget imports `qtwebplot.core.WebBridgeView` and ignores everything above.

## The core (`qtwebplot.core`)

The whole visualization contract is two operations on `WebBridgeView`:

| Direction | Call                              | Arrives as                                          |
|-----------|-----------------------------------|-----------------------------------------------------|
| Py → JS   | `view.send("name", payload)`      | `qtwebplot.handlers["name"](payload)` (if installed) |
| JS → Py   | `qtwebplot.send("name", payload)` | `view.received` signal fires `(name, payload)`      |

`name` is any string; `payload` is anything JSON-marshalable. Backends pick
their own namespaces (`plotly.*`, `bokeh.*`, …) so multiple extensions could
coexist in one view if anyone ever needed it.

### `WebBridgeView` surface

```python
class WebBridgeView(QWidget):
    # content
    def load_html(html: str, *, base_url: QUrl | None = None) -> None
    def load_url(url: QUrl) -> None

    # messaging
    def send(name: str, payload: Any = None) -> None
    received: Signal(str, object)

    # lifecycle
    ready: Signal()                # bridge handshake done
    load_finished: Signal(bool)    # forwarded from QWebEnginePage
    log: Signal(str, str)          # (level, message) — JS console pipe

    # generic export
    def to_png(path) -> Path       # via QWebEngineView.grab()

    # escape hatches
    web_view: QWebEngineView       # property
    bridge: Bridge                 # property — for advanced channel work
    def run_js(src, callback=None) -> None
```

### Bridge bootstrap

Every loaded page gets two `<script>` blocks injected before `</head>`:

1. Qt's `qwebchannel.js` (read at runtime from `:/qtwebchannel/qwebchannel.js`
   — no vendoring required).
2. The core runtime (`qtwebplot/core/_runtime.py::CORE_JS`) which:
   - Polls until `QWebChannel` and `qt.webChannelTransport` are available.
   - Constructs the channel and stores `qtwebplot.bridge`.
   - Calls `bridge.notify_ready()` and flushes any `onReady` callbacks.
   - Exposes `qtwebplot.send(name, payload)`, `qtwebplot.on(name, fn)`,
     `qtwebplot.onReady(fn)`, and `qtwebplot._dispatch(name, payload)` (used
     by Python's `send` over `runJavaScript`).

Messages sent from Python before the bridge is ready are queued (FIFO, max
128, oldest dropped on overflow) and flushed when `ready` fires.

## The convenience layer (`qtwebplot`)

### `PlotBackend` Protocol

```python
class PlotBackend(Protocol):
    def to_html(self) -> str: ...                       # required
    def js_runtime(self) -> str | None: ...             # optional
    def base_url(self) -> QUrl: ...                     # optional
    def on_attach(self, view: WebBridgeView) -> None    # optional
    def on_detach(self) -> None: ...                    # optional
    def set_figure(self, figure: Any) -> None: ...      # optional
```

Backends typically stash the view in `on_attach` so their verbs can call
`view.send(...)`, and connect to `view.received` to surface library-specific
events as typed Qt signals.

### `PlotView(WebBridgeView)`

Thin subclass — holds a backend, injects its `js_runtime()` after the core
bootstrap, calls `load_html(backend.to_html())` on backend change or
`set_figure(...)`. **It adds no visualization verbs of its own.**

## Extensions (`qtwebplot.ext.*`)

Each library lives in its own subpackage and brings its own optional
dependency. Pattern:

- `backend.py` — `XBackend` implementing `PlotBackend`. Adds library-specific
  verbs (e.g. `PlotlyBackend.react`, `BokehBackend.patch`).
- `events.py` — typed event dataclasses + an `XEvents(QObject)` exposing
  signals.
- `_runtime.py` — JS string that subscribes the library's native events and
  forwards them via `qtwebplot.send(...)`, and registers handlers for the
  verbs the backend wants to support.

Verbs use the generic transport — they are *just* `view.send(...)` calls with
the backend's namespace. Nothing magic, nothing hidden.

## Threading

All public methods on `WebBridgeView` / `PlotView` / backends must be called
from the Qt GUI thread. Signals fire on the GUI thread. We don't try to make
the widgets thread-safe — Qt widgets aren't, period. Use a worker thread to
build figures, then `QMetaObject.invokeMethod` or a queued signal to push them
to the GUI thread.

## Asset bundling

For v0 the core JS runtime is inlined as a Python string and `qwebchannel.js`
is loaded from Qt's resource system at runtime. Per-extension JS is similarly
inlined. We can switch to `qrc:` resources or a custom URL scheme handler
later if benchmarks warrant it; the seam is `core/_runtime.py` and each
extension's `_runtime.py`.

## Security

The page is loaded into the user's own application — treat content as
trusted-ish. The core never `eval`s a string received from JS. Python → JS
goes through `qtwebplot._dispatch(name, payload)` which looks up a handler in
a registry; JS cannot use it to reach arbitrary Bridge slots. JS console
forwarding is opt-in (off by default) so app internals aren't broadcast.

## Writing a new backend

1. Subclass nothing — implement the `PlotBackend` Protocol (`to_html` is the
   only required method).
2. In `on_attach(view)`, stash the view and `view.received.connect(...)` to
   handle your namespace's incoming messages.
3. In `js_runtime()`, return JS that calls `qtwebplot.onReady(...)`, then
   subscribes the library's native events and forwards them via
   `qtwebplot.send("<namespace>.<event>", payload)`, and registers any
   Python-callable verbs via `qtwebplot.on("<namespace>.<verb>", handler)`.
4. Expose your verbs as Python methods on the backend that call
   `view.send("<namespace>.<verb>", payload)`.
5. Expose typed signals on an `Events` QObject if you want a richer API than
   raw `view.received`.

See `qtwebplot.ext.plotly` for a worked example.

## Repository map

```
src/qtwebplot/
├── __init__.py              # WebBridgeView, PlotView, PlotBackend, Bridge
├── backend.py               # PlotBackend Protocol
├── view.py                  # PlotView (thin composition)
├── core/
│   ├── bridge.py            # Bridge(QObject) — channel surface
│   ├── web_bridge_view.py   # the core widget
│   ├── _runtime.py          # core JS bootstrap
│   └── _inject.py           # HTML <script> splicing
└── ext/
    ├── plotly/              # PlotlyBackend, PlotlyEvents, runtime
    └── bokeh/               # BokehBackend, BokehEvents, runtime
```

## Bridge instrumentation

Five operability features on `WebBridgeView`:

- **JS console pipe.** `QWebEnginePage` subclass overrides
  `javaScriptConsoleMessage` and emits to `view.log(level, message)` with
  level mapped to `"info"`/`"warning"`/`"error"`. Includes the source location.
- **Debug log.** `view.enable_debug_log()` logs every send/recv with a
  payload preview. Pass a `sink(direction, name, payload, t)` callback for
  custom routing.
- **Per-name throttling.** `view.set_throttle(name, ms)` applies a
  trailing-edge throttle to the `received` signal for messages with that
  name. The latest payload during a cooldown window replays when the window
  expires. Default off.
- **Undelivered-message reporting.** When Python sends a message and JS
  has no handler registered, JS reports back over the bridge and
  `view.send_failed(name, payload_preview)` fires.
- **Bench script.** `tools/bench_bridge.py` measures round-trip latency
  for a range of payload sizes (0 B → 512 KB). Useful for regression checks.

## Status & next items

What's working today:

- Core `WebBridgeView`: bidirectional bridge, ready handshake, command
  queue, HTML injection, JS console pipe, debug log, throttling,
  undelivered-message reporting.
- `PlotView` convenience composition.
- `PlotlyBackend`: `react / restyle / relayout / extend_traces / resize`
  verbs and typed `hover / click / selection / relayout` events.
- `BokehBackend`: `patch / stream / set_property` verbs and typed
  `tap / double_tap / selection / ranges_update` events.
- `WebBridgeView.to_png(path)` via `QWebEngineView.grab()`.
- Multi-visualization layout helpers (`qtwebplot.layouts`):
  `PlotGrid` (eager), `PlotTabs` (lazy by default), `PlotSplitter`.
  `PlotGrid` and `PlotTabs` re-exported at top level. Mix backends freely.
- Linked-event coordination: `grid.link(source, event, to, handler)` on
  all three layout helpers, with auto-teardown when views are removed.
- `HoloViewsBackend` (`qtwebplot.ext.holoviews`): composes `BokehBackend`
  internally — HoloViews → Bokeh model conversion delegates rendering,
  verbs, and typed events to the existing Bokeh backend.
- `Theme` dataclass (`qtwebplot.Theme`) with `light()` / `dark()` /
  `from_qt_palette(...)` / `from_qt_app(...)`. Backends opt in via the
  `apply_theme(theme)` Protocol method; Plotly and Bokeh both implemented.
  `PlotView(theme=...)` applies on attach; `view.set_theme(t)` re-applies live.
- Smoke tests for HTML injection + Theme; pytest-qt GUI tests for the
  bridge handshake, the layout helpers, and linked events.

Tracked next:

- CI matrix + first PyPI alpha release.
- Documentation site (mkdocs-material).
- `load_failed` surfacing (today, a load failure is silent except for
  `load_finished(False)`).
- Plotly offline asset bundling (`plotlyjs="inline"` default vs CDN).
- `MultiPlotView` (Strategy B from `multi-visualization.md`) if/when
  dashboard-scale memory becomes a concern.
