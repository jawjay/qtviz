# Future development ideas — SUPERSEDED (historical)

> **Superseded (2026-07-24).** This catalog predates the `qtwebplot`→qtviz pivot —
> its "Where we are" below describes the old bridge POC, and most of its top bets
> (CI matrix, linked events, docs site, HoloViews, theme propagation, the
> matplotlib backend, binary transport) have long since shipped. The living
> horizon is now [`improvement-plan.md`](improvement-plan.md) (§4, staged
> 0.3→1.0); still-live ideas from this list (streaming, annotation layer, plot
> persistence, toolbar/inspector polish, plugin entry-points, type-checking CI)
> are absorbed or parked there. Kept for the record — statuses below are stale.

A curated, opinionated list. Marked **★** for "I would advocate for this
soon," **○** for "good idea, no rush," **△** for "interesting bet, would
need more info to commit."

## Where we are

The POC works. Three-layer architecture validated against two different
backends. Layout helpers ship. Bridge has instrumentation and measured
latency. Tests cover the seams. No CI, no PyPI, no docs site.

## My top 5 bets, ranked

If I were picking what to do next, in this order:

1. **★ CI matrix + first PyPI release (0.0.1 alpha).** Until this exists,
   the project is hard for anyone but you to try. GitHub Actions on
   macOS/Linux × Py3.11/3.12 with `pytest`, ruff, and one offscreen-GUI
   smoke test. Publish under `qtwebplot` once the name is free. Single
   afternoon of work; unlocks every later idea.

2. **★ Linked-event coordination between views.** The most user-visible
   feature gap. Build it on `PlotGrid` / `PlotTabs`: `grid.link(source=0,
   event="selection", to=[1,2], as_="patch", transform=fn)`. Forces us
   to think about whether coordination belongs in the layout helper or in
   a separate `Linker` object — the right answer falls out once we wire
   one or two real cases.

3. **★ Documentation site (mkdocs-material).** A landing page, a 5-minute
   quickstart, a "writing a backend" tutorial, an API reference. Without
   docs, this looks like a script collection, not a library. Two days.

4. **○ HoloViews backend.** Mostly pass-through to the Bokeh backend
   we already have. Triples the addressable user base (HoloViews is the
   default plotting layer in PyViz / hvPlot / Panel). Low effort, high
   ecosystem reach.

5. **○ Theme propagation from `QPalette`.** Plots that match the host
   app's light/dark mode and accent color. Was in the original design
   doc and is the single biggest polish item — embedded plots that don't
   match the host app feel broken.

Everything below is a catalog organized by theme — not a plan.

---

## Ecosystem reach (more backends)

- **★ HoloViews backend.** Renders via Bokeh (or Matplotlib). Mostly
  pass-through once the renderer is set.
- **★ Altair / Vega-Lite backend.** Vega specs are pure JSON; rendering
  is a single JS call. Cleanest possible backend — pure data, no figure
  objects to wrangle.
- **○ Matplotlib backend.** Two options: `mpld3` for an interactive
  fallback, or just `to_png`-as-image for the rest of the scientific
  Python ecosystem. The second is uglier but ubiquitous.
- **△ Echarts backend.** Popular in some industries (especially China);
  rich gallery; would broaden us beyond the Python-scientific world.
- **△ Custom/raw backend.** A `RawHtmlBackend` and a `CustomJSBackend`
  for users writing their own three.js / deck.gl / D3 from scratch.
  Already half-implementable today by using `WebBridgeView` directly;
  the value is making it a documented first-class story.

## Cross-plot coordination

- **★ Linked events on `PlotGrid` / `PlotTabs`.** See top-5.
- **○ `MultiPlotView` (Strategy B from `multi-visualization.md`).** One
  page hosting many backends. 10× memory savings at the dashboard scale.
  Requires the `to_fragment(slot_id)` backend contract. We deferred it
  until someone hits the wall — that point arrives the first time anyone
  tries to put 20 plots on one screen.
- **○ Synchronized axes.** "When user zooms plot A, zoom plot B to the
  same x-range." Pattern, not a feature — once `link` lands, this is
  one specific instance of it.
- **△ Shared data sources across plots.** A `DataBinding` object that
  multiple backends subscribe to; updating the binding patches every
  bound plot. Powerful for dashboards; tricky for backends that
  serialize data into the figure rather than referencing it.

## Performance

- **○ Asset bundling via `qrc:` resources.** Currently we inline
  `qwebchannel.js` and the core runtime per page. Resource-based loading
  would let Chromium cache them across pages. The bench shows we're not
  bottlenecked here, but it's a clean win.
- **△ Binary fast path for large payloads.** Above ~1 MB JSON becomes
  the bottleneck. Encode as base64 typed arrays or use a custom URL
  scheme for raw bytes. Defer until someone actually pushes a million
  points through.
- **△ Page warm pool.** Pre-instantiate `QWebEngineView`s so backend
  swaps are sub-100ms. Marginal value; complex.

## Developer experience

- **★ Bridge inspector widget.** A `BridgeInspector(view)` Qt widget
  showing live bridge traffic — name, direction, payload, timestamp.
  Built on the existing debug-log hook. ~150 LOC, makes debugging real
  apps dramatically easier.
- **○ Hot reload during development.** File watcher on the user's
  figure script → re-render on change. Niche but loved by anyone who
  uses it.
- **○ Typed payloads.** Move payload shapes from `dict` to `TypedDict`
  or `msgspec.Struct`. Better autocomplete, better refactor safety. We
  pay for it with a sharper dependency surface.
- **○ Plot recording/replay.** Log all bridge messages, replay to
  recreate state. Invaluable for bug reports — "send me your replay
  and I'll repro your crash."

## Production hardening

- **★ CI matrix.** See top-5.
- **○ Type checking in CI.** mypy or pyright over the public API.
  Strictness is the choice — start with `strict_optional`, work up.
- **○ Test coverage gate.** 80% line coverage, exclude examples + tools.
- **○ Pre-commit hooks.** ruff, type check, format. One-liner setup
  via `pre-commit`.
- **○ Sphinx or mkdocs API reference.** Auto-generated from docstrings.
- **○ Semantic versioning policy + deprecation pattern.** Important
  before there are real users.

## Streaming / reactive data flow

- **○ `StreamingBackend` wrapper.** Wraps any backend that supports
  incremental update; subscribes to a Python observable (signal,
  QSignal, asyncio.Queue) and pushes deltas through. Particularly nice
  for sensor / monitoring use cases.
- **△ Reactive figure bindings.** `view.bind(data_signal, fig_builder)`
  — the figure rebuilds whenever the signal fires. Needs careful
  backpressure / coalescing or it'll hammer the bridge.
- **△ WebSocket / ZMQ / MQTT plumbing.** Native sources for the
  streaming wrapper. Probably belongs in an extension package, not core.

## Qt-side polish

- **○ Toolbar widget.** Generic `PlotToolbar(view)` — Reset zoom, Save
  PNG, Toggle log scale, etc. Backend declares which actions it supports;
  toolbar enables them. Mostly UX work.
- **○ Status bar widget.** Live hover position, selection count, etc.
- **○ Theme propagation.** See top-5.
- **△ Drag-and-drop CSV.** Drop a file on a `PlotView`, get a default
  plot of it. Cute but probably not core.

## Novel capabilities

- **○ Headless screenshot mode.** A standalone CLI: `qtwebplot render
  figure.py --backend plotly --output thumb.png --width 800`. Useful
  for automated thumbnailing, CI artifact generation, batch reports.
  Builds on existing `to_png`. Single afternoon.
- **△ Two-way data binding to Qt models.** A `QAbstractItemModel` ↔
  backend data binding. Edits to the model patch the plot; selection
  in the plot updates the model. Bridges Qt's model/view world to JS
  viz. Powerful but design-heavy.
- **△ Annotation layer.** Python-side text/arrow/shape annotations
  drawn over any backend, via a shared transparent overlay. Lets us
  add annotations without backend-specific code. Interesting but the
  alignment math is fiddly.
- **△ Plot persistence.** Save complete view state (figure JSON +
  zoom + selection + theme) as a single file; reload exactly. Bridges
  exploration → reproducibility.

## Plugin / extension story

- **○ Entry-point-based backend discovery.** Third-party packages
  expose backends via `[project.entry-points."qtwebplot.backends"]`.
  Auto-detected on import. Drops the friction of "now write a backend"
  to publish-and-install.
- **△ Backend conformance suite.** A `pytest` parametric fixture set
  any backend can run to validate it implements the contract correctly.
  Pays off once there are 5+ backends.

---

## Things I'd push back on if asked

- **A REST/RPC interface for remote control.** Tempting because "now
  it works from anywhere." Reality: you almost always want the plot
  in-process. The few cases that need remote can use existing tools
  (Streamlit, Panel) or write the relay themselves.
- **A no-code GUI builder.** Cool demo, huge maintenance burden,
  competes with several existing tools. Skip.
- **A new layout DSL** for declaring complex dashboards in Python
  (e.g., Streamlit-style `view.row(a, b).column(c, d.scaled(2))`).
  Reinvents what `QSplitter`/`QGridLayout` already do; the helpers we
  shipped are enough.
- **Cross-process backend isolation.** "Each plot in its own subprocess
  for fault isolation." We already get this for free at the Chromium
  process level when we use separate `QWebEngineView`s. Doing it at the
  Python layer too is over-engineering.
- **Implementing every feature of every backend's API.** PlotlyBackend
  doesn't need every Plotly function as a method. Users reach into
  `backend.figure` and modify it; if `react(...)` doesn't take care of
  it, the figure object is the source of truth.

---

## Suggested decision points

If you want to push this to "real library" status:

- **Pick one ★ from the top-5.** That's the next milestone.
- **Decide on a release cadence.** Quiet (only when there's something
  worth tagging) vs. predictable (every 4 weeks).
- **Decide what's in scope.** Plotting-library extensions go in core or
  in separate packages? My take: in core for the big three (Plotly,
  Bokeh, HoloViews), plugins via entry points for everything else.

If you want to push this to "interesting research" status:

- **Pick a △.** The two-way Qt model binding and the annotation layer
  are the most novel things on this list — there's no other Qt+plot
  library that does either well.
- **Document why it matters.** A blog post or design doc on the idea
  before code. Forces the value prop into the open.

If you want to keep it personal-use:

- **Add the bridge inspector** (top-5 #4, sort of) and **theme
  propagation** (top-5 #5). Those are the two things that make daily
  use noticeably nicer without expanding scope.
