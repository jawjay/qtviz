# Design — W5 Arrow IPC transport for the webengine backend

> The transport design pass for roadmap Phase 5 / `webengine-rehome.md` §8 **W5**.
> Companion to [[discussion-items]] D29 (JSON now, Arrow later — gated on a measured
> need). Goal: ship large figure payloads to the embedded browser as **binary**
> instead of JSON. **No code yet** — this is the design to review and decide first.

## 1. The problem

The webengine backend hosts a Plotly figure in a `QWebEngineView` and ships the
figure's **data** to the browser as **JSON text**. That is fine for moderate
figures (why D29 chose it) but is the ceiling on the data-intensive path:

- **Size.** A `float64` as JSON is ~15–20 ASCII chars; 1M (x, y) points ≈ 30–40 MB
  of text vs ~16 MB of raw `float64`.
- **CPU.** Both ends pay a text tax — Python `to_json` stringifies every number,
  the browser `JSON.parse`s megabytes, then re-parses strings to numbers.
- **Precision.** Floats round-trip through decimal text (lossy unless verbose).

Target (roadmap): **< 100 ms for a representative ~100 MB payload** — a figure JSON
simply cannot deliver interactively.

## 2. As-is — how data crosses the bridge today

```
INITIAL render
  PlotlyBackend.to_html()  → plotly.io.to_html embeds the whole figure (incl. data)
                             as a JSON <script> in the HTML document → view.setHtml()

UPDATES (react / restyle / extend, live data)
  backend.react(fig) → view.send("plotly.react", payload)
       → WebBridgeView._send_now: json.dumps([name, payload])
       → page.runJavaScript("window.qtwebplot._dispatch.apply(qtwebplot, <JSON>)")
       → JS: qtwebplot.handlers["plotly.react"](payload) → Plotly.react(div, data, layout)

EVENTS (JS → Py): qtwebplot.send() → bridge.emit_event() over QWebChannel.
```

So bulk numeric data crosses as JSON in **both** paths (embedded in the HTML, and as
a JSON literal inside a `runJavaScript` source string). The JS bridge API
(`qtwebplot.on(name, fn)` / `_dispatch`) is the hook where a binary path would land.

## 3. What has to change (independent of transport)

Two pieces, separable from the transport choice:

1. **Split the figure into structure + bulk data.** The native-element renderers
   (`_figure.build`) currently inline `x`/`y` as Python lists. They'd instead emit a
   *data-by-reference* figure — small JSON (trace types, layout, names, and a
   `{column_id, dtype, len}` per data array) — and hand the raw arrays to the
   transport separately.
2. **JS reassembly.** A handler decodes the binary blob into **typed arrays** and
   injects them into the trace data before `Plotly.react`/`newPlot`. (Plotly.js
   accepts typed arrays / its `{dtype, bdata}` typed-array spec for trace data —
   **spike: confirm the exact ingestion API and version.**)

This split is the bulk of the work; the transport is how the binary blob gets across.

## 4. Format — Arrow IPC vs. raw typed-array buffers

| | **Arrow IPC** (recommended) | Raw `Float64Array` buffers + tiny JSON header |
|---|---|---|
| Shape | columnar record batch; dtypes, nulls, strings, multi-column in one blob | one buffer per column; you frame dtype/offset/len yourself |
| Fit | qtviz's data layer is **already Arrow-aware** — `to_arrow`/`pyarrow` is natural; zero-copy | minimal; no structure |
| JS side | `apache-arrow` JS → `tableFromIPC` → typed arrays | `new Float64Array(buf)` directly |
| Cost | **+1 JS dependency** (`apache-arrow`, ~100s of KB into the page) | no JS dep, but hand-rolled framing rots as needs grow (categorical color, strings, nulls) |

**Recommendation: Arrow IPC** — it matches the data layer, survives growth
(categorical/`color_by`, datetime, nulls), and is zero-copy. The honest cost is the
`apache-arrow` JS bundle in the page (load via CDN or inline, like plotly.js). Keep
raw-buffers as the fallback if that dep proves unwanted for a minimal build.

## 5. Transport — getting the binary blob to the page

| Option | Mechanism | Pros | Cons | Scales to 100 MB? |
|---|---|---|---|---|
| **A. base64 over the existing channel** | base64 the bytes into the `send()` JSON payload (or HTML); JS `atob`→`Uint8Array` | zero new Qt infra; reuses `send`/`runJavaScript`; works initial + update | +33% size; **still a text step**; a multi-MB `runJavaScript` source literal is heavy to build/parse | ✗ (good to a few MB) |
| **B. custom URL-scheme handler** (`QWebEngineUrlSchemeHandler`) | register a `qtviz` scheme; page `fetch("qtviz://data/<id>")`; handler `job.reply("application/vnd.apache.arrow.stream", QBuffer(bytes))` | **true binary**, no base64, streams; **no open port**; browser handles backpressure | scheme must be registered **before** the QApplication/profile (early-init); handler + buffer-registry lifecycle (free after fetch); per-profile install; security flags (local/CORS) | ✓ |
| **C. local HTTP endpoint** | localhost server serves the bytes; page `fetch("http://127.0.0.1:port/...")` | true binary; standard fetch; no scheme-timing constraint | **opens a TCP port** (bind 127.0.0.1 + per-session token); server thread + lifecycle; CORS | ✓ |
| **D. QWebChannel `QByteArray`** | expose bytes via the Bridge QObject | avoids the giant `runJavaScript` string | QWebChannel **JSON-encodes** a QByteArray → still base64; message-size limits | ✗ |

Pull-model note: B and C reference the data by `id` in the figure structure, and the
handler/server must have those bytes ready (a `{id → bytes}` registry on the Python
side, freed once fetched or on handle dispose).

## 6. Recommendation — phased

- **W5.1 — prove the pipeline (Option A, base64).** Split the figure, ship Arrow
  bytes base64-encoded over the existing `send()` channel, decode in JS → typed
  arrays → Plotly. Minimal infra; establishes the JS-side Arrow + Plotly
  typed-array path and the figure-splitting in `_figure`. Good to a few MB; measure
  against the JSON baseline.
- **W5.2 — scale (Option B, custom scheme handler).** Swap *only the data-blob
  transport* for a binary `fetch` over a registered `qtviz` scheme, hitting the
  < 100 ms / 100 MB target. The W5.1 split + decode pipeline is unchanged; this is
  the transport substitution.

This sequences value-first and keeps each step verifiable, mirroring the W3a/W3b
split. C (local HTTP) is the fallback if scheme registration proves impractical in
the host app.

## 7. Scope & non-goals

- **Plotly only.** Arrow transport targets the native-element → Plotly path (where
  qtviz *controls* the arrays). **Bokeh** has its own binary `ColumnDataSource`
  transport; HoloViews rides Bokeh — out of scope here.
- **`RawFigure` is lower priority.** A user's pre-built figure already carries inline
  data; re-encoding it is possible but deferred — the win is on the data qtviz builds.
- **Threshold-gated**, like datashader auto-routing: route through Arrow only above a
  measured point-count/byte threshold; small figures stay on JSON (no regression, no
  apache-arrow load).

## 8. Open questions (new discussion items)

- **[D33] Transport** — base64 now (W5.1) → custom scheme handler for scale (W5.2).
  Recommend this phasing; decide whether the local-HTTP fallback is worth pre-building.
- **[D34] Format** — Arrow IPC vs raw typed-array buffers. Recommend Arrow IPC
  (matches the data layer); accept the `apache-arrow` JS dependency.
- **[D35] Figure-splitting** — `_figure.build` emits data-by-reference + a JS
  reassembly step. Confirm Plotly's typed-array ingestion API (`{dtype, bdata}`) and
  version as a spike before committing.
- **[D36] Scheme-registration timing** — a custom scheme must be registered before
  the QApplication. Where does qtviz do that (import-time? a one-time
  `qtviz.backends.webengine.init()`?) without imposing on apps that never use it.

## 9. Benchmark plan (do first, per D29 "measured need")

1. **Baseline:** time `to_json` + bridge transfer + JS parse + first paint for the
   native Scatter→Plotly path at N = 100k / 1M / 10M points.
2. **Threshold:** find the N where JSON becomes the bottleneck (and where it's
   perceptible) — that's the auto-route cutoff.
3. **Target:** Arrow path < 100 ms for a ~100 MB payload.
4. Land the benchmark as a `benchmark`-marked test so the win is provable and the
   threshold is tunable (`set_arrow_threshold(...)`, mirroring `set_raster_threshold`).
```
