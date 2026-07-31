# The parity program — post-1.0 vocabulary, axes & power arc

> **Mandate (owner, 2026-07-31).** "Make the library as powerful as possible and
> as easy to use; the expectation is that users will be able to create any
> visualization they would be able to in other popular visualization libraries.
> Be ambitious — go back to the drawing board as much as needed."
>
> This document is the program frame for that mandate: what "parity" means
> honestly ([D83]), the staged increments, and the numbered decisions
> ([D83]–[D95], house style: recommendation + alternatives). Inputs:
> [`matplotlib-support-matrix.md`](matplotlib-support-matrix.md) (the current-state
> gap list), [`matplotlib-capability-review.md`](matplotlib-capability-review.md)
> Part 1 (the benchmark catalog), [`retrospective-1.0.md`](retrospective-1.0.md)
> (load-bearing patterns + ranked demand), [`improvement-plan.md`](improvement-plan.md)
> §1 (the invariants, kept verbatim).

## 0. What does NOT change

The 1.0 invariants stay load-bearing: immutable value-hashed Elements; three
registered backends, core imports none; 100% offline; lazy-first data;
honor-or-warn + capability honesty; **a curated vocabulary you can hold in your
head, with escape hatches** — growth happens element-by-element with the same
conformance bar, never as API sprawl. Standing non-goals stand ([D58]): native
3-D, frame-animation API, cross-backend Overlay, single-vector mixed export.
Semver is respected: everything here is **additive (1.x)**; nothing removes or
changes a frozen name (`Options` removal stays scheduled for 1.1 as promised).

- **[D83] Parity target = the everyday 90%, declaratively; the tail via escape
  hatches.** "Any visualization from other popular libraries" is interpreted as:
  the figures people actually make routinely in matplotlib / plotly / seaborn /
  pyqtgraph — series, distributions, composition (stacks/areas/pies), fields
  (contour), dual axes, calendar time, formatted ticks — must be expressible in
  the qtviz vocabulary and render on every capable backend. It is explicitly
  *not* 1:1 API cloning (`future.md` push-back, reaffirmed): the long tail
  (polar, broken_barh, spectrograms-as-API, …) remains `handle.native()` /
  `RawFigure` territory. *Alternative rejected:* chase the full mpl catalog —
  destroys the curated-vocabulary invariant and can never win on breadth.

## 1. Increment map (each = spec'd → TDD → green → commit)

| # | Increment | Contents | Decisions |
|---|---|---|---|
| 1 | **Series power** | `Curve.step`, `Curve.marker`, `Bars.orient="h"` wired, surface `grid=` toggle | [D84] [D85] [D87] |
| 2 | **Shared-stats honesty** | one binning for `Histogram` everywhere (+ string rules pass through), `Heatmap` in real data coordinates, pyqtgraph parity debts (Image colormap, Heatmap colormap, ErrorBars color/direction) | [D92] [D93] |
| 3 | **Composition vocabulary** | `Area` (filled/stacked, `group=` per [D68] precedent), `Ecdf` (core-computed, step-drawn), `Pie` (mpl+webengine; pg honestly unsupported) | [D84b] [D90] [D91] |
| 4 | **Tick formatting** | `AxisSpec.tick_format` wired: Python format-spec mini-language + named formats, all three backends | [D86] |
| 5 | **Twin axes** | `y2` on the surface + `Element.axis="y2"`; feasibility spike first (R1 for the second axis) | [D88] |
| 6 | **Fields** | `Contour` (line + filled), gridded like `Image` | [D89] |
| 7 | **Calendar time** | datetime dtype through the data layer + `scale="time"` honored — **reopens [D62]; owner confirm at this boundary** | [D94] |
| 8 | **Interaction ease** | `View(toolbar=True)` (native toolbar where the backend has one), mpl interactive brush | [D95] |

Ordering rationale: 1–2 are small, high-frequency wins and pay honesty debts
before building on them; 3–4 complete "everyday figures"; 5–6 are the two
top-demand parked items (retrospective §4.5); 7 is the biggest lift and needs
an owner call; 8 is polish that benefits from everything before it.

## 2. Decisions

- **[D84] `Curve` grows `step` and `marker`.**
  `step: None|"pre"|"mid"|"post"` (mpl `drawstyle=steps-*`; pyqtgraph
  `stepMode="left"/"center"/"right"` on `PlotDataItem`; plotly
  `line_shape=vh/hvh/hv`) and `marker: None|<the 5-marker vocab>` (mpl
  `marker=`, pg `symbol=`, plotly `mode="lines+markers"`). *Alternative:* a
  separate `Step` element — rejected: a step curve is a rendering mode of the
  same data, not a new data shape; mirrors how every benchmark library models it.
- **[D84b] `Area` is a new element, stacking via `group=`** —
  `Area(data, x=, y=, group=None, mode="overlay"|"stacked", color=, alpha=, label=)`.
  Fill-to-baseline single series; with `group=`, one filled band per category,
  stacked cumulatively when `mode="stacked"` — the exact [D68] `Bars.group`
  pattern, keeping stacking *inside one element* so Elements stay independent.
  *Alternative:* `Curve(fill=...)` — rejected for stacked (cross-element state);
  *alternative:* `Spread` reuse — rejected (different semantics: baseline fill
  + stacking vs an explicit lo/hi band).
- **[D85] `Bars.orient="h"` gets wired on all three backends** (mpl `barh`,
  pg `BarGraphItem` horizontal geometry, plotly `orientation="h"`), including
  grouped/stacked, removing a warn-and-degrade that hits real dashboards.
- **[D86] Tick-format vocabulary = Python format-spec strings + two named
  formats.** `AxisSpec.tick_format`: `"auto"` (today's behavior), a Python
  format spec (`".2f"`, `",d"`, `".0%"`, `".2e"`), or `"eng"` (SI prefixes).
  Translation per backend: mpl `FuncFormatter`/`EngFormatter`; plotly d3-format
  (same spec family — direct passthrough for the common cases); pyqtgraph a
  formatting `AxisItem`. Unknown strings → `ValidationError` at construction
  (fail loud, not at render). *Alternative:* d3-format strings as the canonical
  language — rejected: Python users should write Python format specs.
- **[D87] `OverlayOptions(grid=True)` surface toggle.** One bool, themed color
  as today; per-axis grid control deferred until someone asks. Fixes "grid
  can't be turned off" (§11 of the support matrix).
- **[D88] Twin axes: a `y2` `AxisSpec` on the surface + `axis="y2"` on data
  elements.** `OverlayOptions(y2=AxisSpec(...))`; series elements gain
  `axis: "y"|"y2"`. Backends: mpl `twinx`; pyqtgraph second `ViewBox` +
  right `AxisItem` (the documented pg pattern); plotly `yaxis2` overlaying.
  R1: `RangeEvent` stays primary-axes; y2 range rides `ViewState` as a new
  optional field (additive). **Spike first** (a day-scale feasibility pass per
  the retrospective's "spike the one load-bearing risk"): pg's linked-ViewBox
  resize dance and log-on-y2 interactions are where it can go wrong.
  *Alternative:* full mosaic of per-element axes (mpl `secondary_xaxis` style
  transforms) — rejected: dual-y covers the demand; arbitrary N-axes is sprawl.
- **[D89] `Contour` is gridded (the `Image` data contract), backend-native
  contouring.** `Contour(values2d, bounds=, levels=10|[...], filled=False,
  colormap=, line_width=, label=)`. mpl `contour/contourf`; plotly `contour`
  trace; pyqtgraph `IsocurveItem` per level (lines; `filled` warns-and-degrades
  on pg — capability-honest). Accepting engine-computed contours (documented)
  rather than shipping one contouring algorithm: unlike box-stats ([D67]),
  contour geometry differences are sub-pixel and the algorithms are heavy.
  *Alternative:* depend on `contourpy` for identical geometry everywhere —
  kept open as a follow-up if visual diffs ever matter.
- **[D90] `Pie(data, values=, labels=, hole=0.0)` on matplotlib + webengine;
  pyqtgraph honestly unsupported.** Negotiation already routes an element to
  backends that support it — the `RawFigure` precedent (an element need not
  render everywhere). pg gains it later only if someone actually asks.
- **[D91] `Ecdf(data, column=)` computes in core `_stats` (the [D67] rule:
  qtviz decides the numbers), renders as a post-step curve** via each
  backend's step path — lands after [D84].
- **[D92] pyqtgraph pays its parity debts:** `Image.colormap` (via
  `pg.colormap.get`, warn-fallback to viridis for names pg lacks) and
  `Heatmap.colormap`; `ErrorBars.color` + `direction` (x/both whiskers).
  `Image.interpolation` stays unhonored on pg (no clean primitive; keeps its
  warning).
- **[D93] Histogram bins are computed once, in core.** `core/_stats.histogram`
  (thin wrapper over `np.histogram` accepting int or the numpy rule strings
  `"auto"/"fd"/"sturges"/…`) feeds **all three** backends pre-binned bars —
  today three engines bin differently (np on pg, `ax.hist` on mpl, plotly
  client-side), so the same `Histogram` draws different charts per backend,
  which violates the [D67] shared-numbers principle. webengine switches from a
  `histogram` trace to a pre-binned `bar` trace. String rules stop being
  silently collapsed to `"auto"` (support-matrix wart #4).
- **[D94] Datetime axes get reopened as increment 7 — owner confirmation
  required at that boundary** (this reverses the [D62] parking; the parity
  mandate is the "demand" that ruling anticipated). Sequenced last of the big
  lifts; starts with the dtype-propagation feasibility pass improvement-plan
  risk #3 prescribed (accessors → resolve → transport → backends).
- **[D95] `View(toolbar=True)`** attaches the backend's native toolbar where
  one exists (mpl `NavigationToolbar2QT`; webengine Plotly modebar toggle; pg
  no-op — its mouse interaction is already native), plus an interactive
  mpl rubber-band brush (`RectangleSelector` → `SelectEvent`) so `brush`
  stops being programmatic-only there.

## 3. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Vocabulary growth erodes "hold it in your head" | every element passes the [D54] curation bar: common in ≥2 benchmark libraries, portable to ≥2 backends, honest capabilities elsewhere |
| 2 | Twin axes destabilize the axis seam (the 0.3 R1 lesson) | spike before increment 5; y2 events/state additive-only |
| 3 | Datetime ripples wider than axes (improvement-plan risk #3) | own feasibility pass; owner go/no-go at the boundary ([D94]) |
| 4 | Shared histogram binning changes what existing users see on webengine | it's a bug fix by the [D67] standard; CHANGELOG calls it out loudly |
| 5 | This program re-becomes an unreviewed feature march | the mandate explicitly grants the march, but each increment still lands as its own green commit with its decisions recorded here — reversible, auditable |

## 4. Acceptance (program-level)

A gallery page of "the everyday figures": step chart, area + stacked area,
horizontal grouped bars, pie/donut, ECDF, contour (line + filled), dual-axis
telemetry, formatted ticks (`%`, SI), time-series with calendar ticks — each
rendered from one Element tree on every backend that declares the capability,
exported via `handle.export`, with honor-or-warn covering every new option.
