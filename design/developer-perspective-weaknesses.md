# qtviz 0.1 — the developer's-perspective weakness analysis

> **Purpose.** `EVALUATION.md` assesses qtviz *strategically* (an outside evaluator,
> from the docs). This document is the opposite lens: a **working developer at the
> keyboard**, who could just `import matplotlib` / `pyqtgraph` / `bokeh` / `plotly` /
> `holoviews` and write code directly — and what they *give up, fight, or cannot do*
> by going through qtviz instead, as the code actually stands at the **end of 0.1**.
>
> **Grounding.** Every qtviz claim here is from the source as of `v0.1.0`
> (`file:line` cited), not from the design docs' intentions — several findings below
> contradict what the prose implies. Companion: `capabilities-gaps.md` (the gap
> register) and `EVALUATION.md` (the strategic view). The point is not to talk qtviz
> down — it is to see the abstraction tax clearly so 0.2+ can pay it down where it
> matters.

---

## 0. The one-sentence framing

qtviz's value proposition is **"describe a plot once, render it natively-Qt /
matplotlib / web, offline, at big-data scale."** The tax a developer pays for that
unification is a **lowest-common-denominator surface**: the `Element` API can only
express what is *common and modelled*, and the moment a developer needs a feature
that a single underlying library has but qtviz hasn't modelled, they hit one of three
walls — a **gap** (planned, not built), a **leak** (the abstraction can't express it),
or a **silent drop** (qtviz accepts the parameter and ignores it). The first is
forgivable in a 0.1; the third is the most damaging, because it makes the API
*untrustworthy*.

---

## 1. Cross-cutting weaknesses (felt against *every* direct library)

### 1.1 Silent degradation — the trust bug (severity: **high**)

qtviz's own spec promises backends "differ only in *declared* capabilities and
*declared* degradations — **never in silent behavior**" (`development-plan.md` §3.4).
The code violates this in at least seven places. A developer sets a parameter, sees
no error, and gets no effect:

| You set… | What happens | Where |
|---|---|---|
| `Scatter(marker="square")` | **dropped on all 3 backends** — no renderer passes `symbol`/`marker` | `backends/pyqtgraph/_renderers.py:58`, `matplotlib/_renderers.py:53`, `webengine/_figure.py:87` |
| `Scatter(..., alpha=0.3)` on pyqtgraph | **ignored** — brush set without alpha | `backends/pyqtgraph/_renderers.py:60-69` |
| `Curve(..., line_style="dashed", alpha=…)` on pyqtgraph | **ignored** — pen uses color+width only, no dash | `backends/pyqtgraph/_renderers.py:79-84` |
| `Heatmap(..., aggregator="sum")` | **no-op on every backend** — `grid[y,x] = z  # last value wins (aggregator TODO)` | `backends/pyqtgraph/_renderers.py:197` |
| `Bars(..., group=…)` | **stored, never read** — no grouped/stacked bars exist | (no consumer in `backends/`) |
| `Image(..., interpolation="bilinear")` | **never passed to a renderer** | `elements/image.py` |
| `Options(color=…, alpha=…, label=…)` | **dead type** — exported in `__init__.py:31`, but no element takes `options=` and no renderer reads it | `core/options.py:21` |

A developer using matplotlib directly *never* experiences this: `marker="s"` always
draws squares. This single class of issue does more to erode "can I trust this API?"
than any missing feature. **Fix shape:** reject-or-honor at construction (the
`_validate` taxonomy already exists — extend it to "this backend cannot honor X").

### 1.2 The lowest-common-denominator ceiling (severity: **high**, inherent)

qtviz models **8 elements** (`Scatter, Curve, Bars, Histogram, Image, Heatmap,
ErrorBars, Spread`). Every comparison library has dozens. There is **no** Box/Violin,
Contour, Quiver/streamplot, Graph/Network, Sankey/Chord, Candlestick/OHLC, stacked/
grouped bars, pie, polar, or any 3-D element — despite `Capabilities.dimensions`
*declaring* `{2,3}` on mpl/webengine (`core/capabilities.py`), there is **no 3-D
renderer for anything** (aspirational flag, no code). A developer doing exploratory
analysis routinely needs one of these and must leave qtviz to get it.

### 1.3 No axis transforms — table stakes, missing (severity: **high**, planned)

All axes are **linear, numeric, auto-ranged**. Zero occurrences of `setLogMode`
(pyqtgraph), `set_xscale`/`symlog` (mpl), datetime axis, inverted axes, or
user-settable limits anywhere in `src/` (the only `setXRange`/`set_xlim` are in
zoom-state *restore*, not a public API). Every one of the five comparison libraries
gives `logy`, a datetime x-axis, and fixed limits as a one-liner. This is the single
most common thing a developer will reach for and not find. (Roadmap §8.3 Phase B is
spiked but unshipped.)

### 1.4 The interaction ceiling (severity: **medium-high**, partly inherent)

Interaction is exactly **five typed events** (`Range/Pick/Select/Hover/Tap`,
`core/event.py:24-54`) — a deliberately small, backend-portable set. The cost:

- **No ROIs, no crosshair, no draggable infinite/region lines, no context menus, no
  keyboard, no double-click** — all of which pyqtgraph and Bokeh/Plotly expose
  directly.
- **Select is rectangle-only natively** (Shift+drag, `pyqtgraph/_interaction.py:58`);
  **lasso collapses to a bounding box** (`webengine/_translate.py:89`) — you cannot
  get a true polygon selection's membership.
- **No raw signal access.** With pyqtgraph directly you wire any Qt signal; here the
  five events are the *only* channel out.
- **No row identity through a datashaded raster** — `HoverEvent.value` gives the
  aggregated number, but pixel→source-rows (for linked brushing on big data) is not
  built (`capabilities-gaps.md` §1) — which undercuts the headline big-data story.

### 1.5 Legend & colorbar poverty (severity: **medium**)

Legends exist for **exactly two cases**: a native `Scatter(color_by=…)` and a
datashaded raster. There is **no legend for Curve, Bars, Histogram, ErrorBars,
Spread, Heatmap, Image, or for any multi-series overlay**; **no legend-position
control**; pyqtgraph's continuous "colorbar" is a **5-stop stepped swatch, not a
gradient** (`pyqtgraph/_legend.py`); and **webengine renders no legend for anything**
(`showlegend: False` hardcoded, `webengine/_figure.py:293`). A two-series overlay —
the most basic chart there is — has no way to say which line is which. Every direct
library labels a multi-series plot for free.

### 1.6 Export poverty (severity: **medium**)

`Capabilities.exports`: pyqtgraph `{png}` (SVG exists in code but is unadvertised as
"fragile"), webengine `{png}` only (SVG/PDF would need kaleido), matplotlib
`{png,svg,pdf}`. **Composite/mixed-backend layouts raise on export** — there is no
single surface to render. So the "use mpl for publication export" pitch holds only if
your whole figure is mpl-renderable through the 8-element LCD; the moment you compose
a mixed-backend dashboard, you cannot export it at all.

### 1.7 The escape-hatch asymmetry (severity: **high**, structural)

When a developer outgrows the LCD, the *only* exit is `RawFigure` — and it
**abandons the entire value proposition**:

- It hosts **only Plotly / Bokeh / HoloViews**, and **only on the webengine backend**
  (`webengine/render.py:138`). You **cannot** drop in a hand-built matplotlib `Axes`
  or a pyqtgraph `PlotItem` — the two *native* backends have no RawFigure renderer at
  all. So the escape hatch routes you *off* native-Qt and *into* a browser view.
- A RawFigure **can't compose** — it raises `IncompatibleOverlayError` in an Overlay
  (`webengine/_figure.py:243`) and is a standalone pane in a Layout.
- It loses **theming** (your Theme isn't applied), **datashader**, **reactivity**
  (it's static), and for **Bokeh/HoloViews** figures it loses **Pick events and
  row-index selection** too (`webengine/_translate.py:120`).

In other words: the abstraction is all-or-nothing. The instant you need one feature
it doesn't model, you don't get "qtviz plus a little raw access" — you get "a web
view of a foreign figure, with qtviz's benefits switched off." Contrast HoloViews,
where `.opts(hooks=[...])` hands you the live Bokeh/mpl object *inside* the managed
plot.

### 1.8 The double learning curve & ecosystem gap (severity: **medium**, time-based)

- To be productive you must learn **qtviz's model *and*** the backend you will
  inevitably drop to. A pyqtgraph or matplotlib developer already knows the lower
  layer; qtviz adds a layer without removing the need for the old one.
- **Zero ecosystem.** No Stack Overflow answers, no third-party tutorials, no
  generative-model fluency, one maintainer, pre-release API churn. "How do I X in
  matplotlib" has 10,000 answers; "how do I X in qtviz" has the source. For many
  teams this alone outweighs the abstraction's benefits.
- **Debugging is two layers deep.** A wrong-looking plot could be your spec, the
  negotiation, the renderer, or the backend — versus one layer when you call the
  library directly.
- **Dependency drift risk.** The HoloViews adapter and Datashader path are pinned
  ranges; the abstraction's correctness rides on libraries that move independently.

---

## 2. Per-library: what a developer gives up by routing through qtviz

Each section: what that library is *uniquely good at*, and the concrete tax qtviz
imposes versus using it directly.

### 2.1 vs. **matplotlib** (the publication/export & breadth king)

**Direct strengths:** the full Artist API; every axis scale (log/symlog/logit/
datetime); annotations, text, arrows, spans; `GridSpec`/subplots/twin axes; ~60 plot
types; seaborn/plotnine declarative grammars on top; best-in-class SVG/PDF/EPS export.

**The tax through qtviz:**
- You reach matplotlib through the **8-element LCD** — no `annotate`, no `axhline`/
  `axvspan`, no `twinx`, no `GridSpec`, no contour/quiver/violin, no log/datetime
  axis (§1.3). The single biggest reason people pick matplotlib (it can draw
  *anything*) is exactly what the abstraction hides.
- **No raw `Axes` escape hatch** (§1.7) — `RawFigure` can't host matplotlib. So when
  you need one `ax.annotate`, you can't "just reach in"; you leave qtviz entirely.
- Export breadth survives (`{png,svg,pdf}`) **only for all-mpl figures**; a composed
  mixed-backend figure can't export at all (§1.6).
- `matplotlib_rasterized=True` is exposed on Scatter — a rare *honored* per-backend
  knob — but it's the exception that proves how thin the per-backend surface is.

**Net:** a developer who chose matplotlib *for its breadth and export* gets the
export (sometimes) and almost none of the breadth.

### 2.2 vs. **pyqtgraph** (qtviz's own native engine)

This is the sharpest irony: qtviz is *built on* pyqtgraph, yet a developer using
pyqtgraph **directly** gets strictly more native power.

**Direct strengths:** `ROI`/`LinearRegionItem`/`InfiniteLine`/crosshair; `ImageView`
with histogram-LUT + interactive levels; `GLViewWidget` true 3-D; custom `AxisItem`
(log, datetime, custom ticks); per-curve `setData` real-time streaming; arbitrary Qt
signals; right-click context menus; multiple linked view boxes with independent axes.

**The tax through qtviz:**
- **All of the above interactivity is gone** — replaced by 5 events (§1.4). No ROI,
  no crosshair, no region selector, no draggable handles, no LUT widget.
- qtviz even **drops pyqtgraph styling it could pass through**: `marker`, `alpha`,
  `line_style` are silently ignored on the pyqtgraph backend (§1.1). Raw pyqtgraph
  honors all three.
- **No 3-D** despite the engine supporting it.
- **No escape to the raw `PlotItem`** (§1.7) — you can't grab the underlying item to
  add one `InfiniteLine`.
- You pay an **abstraction + negotiation layer** for a backend you could have called
  in the same number of lines for a simple scatter.

**Net:** for an *interactive native desktop app* — pyqtgraph's home turf and qtviz's
stated wedge — a developer loses most of pyqtgraph's interactive vocabulary and some
of its styling, in exchange for portability they may not need if they've already
committed to Qt.

### 2.3 vs. **bokeh** (rich web interactivity & linked widgets)

**Direct strengths:** `CustomJS` callbacks; `HoverTool` with templated tooltips;
`Tap`/`BoxSelect`/`LassoSelect` with real index callbacks; linked brushing across
many figures via shared `ColumnDataSource`; widgets/layouts; server apps; large glyph
set; themes; legends/annotations.

**The tax through qtviz:**
- Bokeh is reachable **only via `RawFigure` on webengine** — so **standalone, no
  compose, no theme** (§1.7).
- **Worst event fidelity of any host:** a Bokeh `RawFigure` emits **only Tap +
  Select(bounds, *empty* indices) + Range** — **no Pick, and selection carries no row
  indices** ("a Bokeh SelectionGeometry carries the brushed region, not row indices",
  `webengine/_translate.py:120`). The thing Bokeh is *best at* — selection-driven
  linked brushing with real indices — does not survive the trip.
- No `CustomJS`, no templated hover, no widgets, no `showlegend` (webengine forces it
  off, §1.5).

**Net:** routing Bokeh through qtviz delivers a static-ish picture of a Bokeh figure
and discards its interaction model. A Bokeh developer gets almost nothing from qtviz.

### 2.4 vs. **plotly** (3-D, animation, hover, trace breadth)

**Direct strengths:** 3-D surface/scatter/mesh; frame animations + range sliders;
`hovertemplate`; a huge trace vocabulary (choropleth, sankey, candlestick, treemap,
parcoords…); faceting; the built-in modebar.

**The tax through qtviz:**
- Two routes, both lossy. **Native webengine** maps only the 8 elements to Plotly
  traces — **no 3-D, no animation, no hovertemplate, and no legend at all**
  (`showlegend:False`, §1.5). **`RawFigure`** gives you a full Plotly figure with good
  events, but **standalone, un-themed, un-composable** (§1.7).
- So you choose between *(a) qtviz's compose/theme/events but only LCD Plotly* and
  *(b) full Plotly but none of qtviz's integration.* You can't have a composed,
  themed dashboard that also uses a Plotly 3-D surface in one pane with native events.
- **No legends on the native webengine path** is a glaring regression vs. Plotly's
  automatic legends.

**Net:** a developer who chose Plotly for 3-D/animation/trace-breadth must use
`RawFigure` and thereby opt out of the qtviz model; the native path gives a
legend-less subset.

### 2.5 vs. **holoviews** (the closest rival — and the model qtviz copies)

This is the most important comparison because HoloViews *is* the "describe once,
render many" idea, and a HoloViews developer is qtviz's most natural convert.

**Direct strengths:** a very large element vocabulary (Sankey, Chord, Graph, HeatMap,
BoxWhisker, Violin, Distribution, Spikes, Sankey, GridSpace, HoloMap…); `.opts(...)`
for deep per-backend styling *without leaving the abstraction*; three mature backends
incl. true gradient colorbars and rich legends; first-class Datashader with all its
options; **bidirectional** `Stream`s; `DynamicMap` with auto-generated widgets;
`.hooks` to reach the live backend object.

**The tax through qtviz:**
- The adapter is **one-way and partial**: `from_holoviews` translates only the 8
  overlapping elements; **everything else falls back to `RawFigure`** → webengine,
  standalone (§1.7). A HoloViews `Layout` mixing a Sankey and a Curve loses its
  composition.
- **No `.opts()` fidelity** — HoloViews users live in `.opts(...)`; qtviz has no
  equivalent escape into per-backend styling. The styling you get is qtviz's `Theme`
  + the thin element kwargs.
- **No bidirectional streams** (HoloViews `Stream` ⇆) — qtviz's `DynamicMap` support
  is one-way `→ Signal[Node]` re-render (L2 + the `.qtviz` accessor are deferred,
  roadmap §3). The linking that makes HoloViews powerful is half-present.
- **Legends/colorbars are richer in HoloViews** on every backend (§1.5).

**Net:** qtviz gives a HoloViews developer a native-Qt rendering of the *subset* of
their work that overlaps qtviz's 8 elements, and a web view for the rest — minus
`.opts`, minus full streams. The pitch ("HoloViews, but native Qt") holds only for
simple, in-vocabulary plots.

---

## 3. Severity-ranked synthesis (for roadmap prioritization)

Tagged **bug** (accepts-then-ignores; violates the spec), **gap** (planned, not
built), **leak** (the abstraction structurally can't express it).

| # | Weakness | Kind | Hurts most vs. | Suggested 0.2 move |
|---|----------|------|----------------|--------------------|
| 1 | Silent param drops (`marker`, pyqtgraph `alpha`/`line_style`, Heatmap `aggregator`, `Bars.group`, `Image.interpolation`, dead `Options`) | **bug** | matplotlib, pyqtgraph | Honor-or-reject via `_validate`; delete or wire `Options`. **Cheapest credibility win.** |
| 2 | No log/datetime/limit/invert axes | gap | all five | Ship axis-surface Phase B (already spiked). |
| 3 | Escape-hatch abandons everything & can't host mpl/pyqtgraph | leak | all five | A *native* raw-item hook (drop a `PlotItem`/`Axes` into a pane) + `.hooks`-style access. |
| 4 | Element vocabulary (8) — no Box/Violin/Contour/Graph/3-D/grouped bars | gap/leak | matplotlib, holoviews | Prioritize Box/Violin + grouped/stacked bars + a real Heatmap agg. |
| 5 | Legend poverty; webengine none | gap | plotly, bokeh, holoviews | Legends for overlays/Curve/Bars; webengine legend; true gradient colorbar. |
| 6 | Interaction ceiling; no row-id through rasters | gap/leak | pyqtgraph, bokeh | Raster pixel→rows (roadmap §8.4); a crosshair/region primitive. |
| 7 | Bokeh/HoloViews RawFigure: no Pick, no select indices | gap | bokeh, holoviews | Finish the Bokeh selection→indices map (W3b). |
| 8 | Export: PNG-centric; no composite export | gap | matplotlib, plotly | Composite export surface; advertise/firm up SVG. |
| 9 | Ecosystem/maturity/double-learning-curve | time | all five | Docs depth, recipes, stability commitments — not code. |

**The cheapest, highest-trust win is #1**: it is mostly *deletion and validation*, not
new features, and it directly attacks the "can I trust this API?" doubt that an
evaluating developer forms in the first hour.

---

## 4. Where the tax is worth paying (balance)

So this isn't read as a teardown: the weaknesses above are the *cost* side of a trade
that still has a real benefit side (detailed in `EVALUATION.md`). For the **narrow
profile qtviz targets** — a PySide6 desktop app, offline, that needs *both* fast
native interaction *and* publication export of the *same* simple-to-moderate plots,
over big/lazy data — the LCD covers the common case and the unification is genuinely
unmatched. The weaknesses bite when a developer needs (a) breadth beyond the 8
elements, (b) deep per-backend control, or (c) the rich interaction of the web
libraries. The 0.2 priorities in §3 are precisely the moves that widen the band of
"plots where the tax is worth it."
