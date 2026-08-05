# Feasibility report — the axis-surface seam

> **Question.** Can qtviz gain a single, backend-agnostic "axis surface" through
> which a plot's surface-level concerns — title, axis labels, **scale**
> (log/symlog/time), **limits**, inversion, aspect, **tick formatting**, legend —
> are *declared* once and *applied* consistently on every backend, while
> interaction (pan/zoom range, brush bounds, picks) flows back through that same
> surface in stable data coordinates?
>
> **Short answer.** **Yes — high feasibility, and lower-risk than it looks**,
> because the attachment point already exists in the data model and was already
> specified; it is simply wired into *zero* backends today. The core properties
> (title, labels, log scale, limits, invert, aspect, legend on/off) map onto a
> native primitive in all three backends. The genuine work is in two places, not
> the seam itself: (1) **coordinate normalization under log scale on pyqtgraph**,
> and (2) **graceful degradation** for scales/formats a backend can't do
> (symlog, logit, time on some backends). Both fit existing house patterns.
>
> Investigation only — **no code is changed by this report.** Companion to
> [`matplotlib-capability-review.md`](matplotlib-capability-review.md) §2.1 (Axes/
> scales/ticks) and [`capabilities-gaps.md`](capabilities-gaps.md) §2 (axis
> transforms). Scope is **item #1, the foundational seam** — log/datetime/twin-axes
> are downstream consumers, sequenced at the end.

---

## 1. Current state — what exists, what's dead

### 1.1 The attachment point exists and is specified

`OverlayOptions` already models the shared surface and the spec is explicit about
its role:

- `core/options.py:37-54` — `OverlayOptions(title, x_label, y_label, legend, background)`.
- `core/compose.py:29` — every `Overlay` carries one (`self.options = options or OverlayOptions()`).
- `design/spec.md:406-421` — *"an explicit container for shared-axes/title/legend
  concerns … When set on `Overlay`, these win over any child's per-element label."*

### 1.2 …but no backend reads it

Grepping every renderer: **`title`, `x_label`, `y_label` are never consumed.**
The only `OverlayOptions` field that does anything is *nothing* — even `legend`
and `background` are unread (background comes from `Theme`, not the options).

- pyqtgraph `_render_cell` (`backends/pyqtgraph/render.py:146-153`) builds a
  `PlotItem`, calls `style_plot(plot, theme)`, then renders elements. It never
  touches `node.options`.
- matplotlib `_render_cell` (`backends/matplotlib/render.py:143-151`) gets an `ax`,
  calls `apply_theme_ax(ax, theme)`, then renders elements. Same — `options`
  ignored.
- webengine `plotly_layout` (`backends/webengine/_figure.py:254-275`) builds the
  layout dict from the `Theme` only; no `options` thread through.

The Phase-1 acceptance milestone wired only `LayoutOptions.link_x/link_y`
(spec.md:446); `OverlayOptions` was defined and parked. **So the surface fields are
a latent correctness gap today** (a user setting `title=` sees nothing), and that
is the seam we are completing.

### 1.3 What already styles the axes (the sibling step)

Each backend *already* has a per-surface "apply" step — but it only does **visual**
theming, not **semantic** axis config:

| Backend | Existing per-surface step | What it sets |
|---|---|---|
| pyqtgraph | `style_plot(plot, theme)` (`pyqtgraph/_theme.py`) | axis pen/text colors, grid on |
| matplotlib | `apply_theme_ax(ax, theme)` (`matplotlib/_theme.py`) | facecolor, spines, tick colors, label colors, grid |
| webengine | `plotly_layout(theme)` (`webengine/_figure.py:254`) | bg, font, gridcolor, colorway |

**Key structural fact:** the surface-config apply step is a *direct sibling* of an
already-existing, already-called theming step, at a hook point that already exists
in all three backends. We are not inventing a new pipeline stage — we are adding a
second call right next to one that's already there.

### 1.4 Interaction already implies a surface

Interaction state is already surface-scoped and already in **data coordinates**:

- `ViewState(x_range, y_range, selection)` (`core/backend.py:24-31`) — captured and
  restored per backend across rebuilds/backend-swaps
  (`pyqtgraph/render.py:54-68`, `matplotlib/render.py:54-68`).
- `RangeEvent(x, y)`, `SelectEvent(bounds)`, `PickEvent(x, y)`, `HoverEvent(x, y)`
  (`core/event.py:24-55`) — all carry data-space coordinates.
- `View._install` restores a pending `ViewState` *after* render (`core/view.py:142-144`).

So the surface concept is *implicit* in the interaction layer already. The seam
makes it *explicit* and gives it an owner — which matters once scales are
non-linear (see §4).

---

## 2. Proposed design

### 2.1 The shape: a config object + one apply step per backend

```
            describe (immutable)                 apply (per backend, once per surface)
 ┌─────────────────────────────┐      ┌──────────────────────────────────────────────┐
 │ Overlay.options : Surface    │      │ pyqtgraph: apply_surface(plot, surf, theme)   │
 │   title, legend, background  │      │ matplotlib: apply_surface(ax,  surf, theme)   │
 │   x: AxisSpec, y: AxisSpec    │ ───▶ │ webengine:  fold surf into plotly_layout(...) │
 │     scale, label, lim,       │      └──────────────────────────────────────────────┘
 │     invert, tick_format       │                 called in each _render_cell,
 └─────────────────────────────┘                 right after the theme step (§1.3)
```

- **`AxisSpec`** (new, `Immutable`, hashable) — per-axis: `label`, `scale`
  (`"linear" | "log" | "symlog" | "time"`), `lim: (lo, hi) | None`, `invert: bool`,
  `tick_format` (`"auto" | "si" | "percent" | "datetime" | f"fixed:{n}"`).
- **Surface options** — `title`, `legend`, `background`, `aspect`, and an `x`/`y`
  `AxisSpec` pair. **Recommendation: extend the existing `OverlayOptions`** rather
  than introduce a parallel type — it already *is* "the shared-surface container"
  per spec, and reusing it keeps the public surface small (a stated project value).
  `x_label`/`y_label` become conveniences that populate `x.label`/`y.label`.

### 2.2 Where it attaches (the one real design question)

A bare `Scatter(...)` has no `Overlay` wrapper, yet must be able to carry a scale.
Three resolutions, in order of preference:

1. **Normalize on render (recommended).** Add a tiny pure helper
   `surface_of(node) -> OverlayOptions` in core: returns `node.options` for an
   `Overlay`, a module default otherwise. Every `_render_cell` already receives the
   node (Element *or* Overlay), so it calls `apply_surface(surface, surface_of(node), theme)`.
   A bare element gets defaults; an `Overlay([el], options=...)` gets its config.
   **This requires no new public type and no change to `Element`.**
2. **Ergonomic sugar (optional, additive).** A HoloViews-style combinator —
   `node.opts(x_scale="log", title="…")` returning `Overlay((node,), options=…)` —
   so users needn't hand-wrap a single element. Pure convenience over (1); can land
   later.
3. **Per-element surface field** — rejected: bloats every `Element`, duplicates the
   `Overlay.options` channel, and muddies "Element = a trace, Overlay = a surface."

**Layouts need no change.** Each `Layout` child is itself a surface-bearing node;
both backends already iterate children and call `_render_cell(child, …)`
(`pyqtgraph/render.py:137-144`, `matplotlib/render.py:132-141`), so per-pane axis
config falls out for free. Figure-level title stays on `LayoutOptions.title`.

### 2.3 Capability-gated scales (fits existing pattern)

Not every backend can do every scale (§3). Extend `Capabilities`
(`core/capabilities.py`) with `scales: frozenset[str]` (and optionally
`tick_formats`). When a surface requests a scale a backend lacks,
**warn-and-fall-back to linear** — exactly the house pattern already used for
`scale="datashader"` falling back to native (spec.md:1364) and for mixed-pane
`link_x` warning-and-ignoring (spec.md:446-448). This keeps "describe once, render
anywhere" honest: the description never *fails* on a weaker backend, it degrades
visibly.

---

## 3. Cross-backend feasibility matrix

The heart of the report: can each backend actually do each property? Native
primitive per backend, or the degradation if not.

| Surface property | pyqtgraph | matplotlib | webengine (Plotly) | Feasibility |
|---|---|---|---|---|
| **title** | `plot.setTitle(t)` | `ax.set_title(t)` | `layout.title.text` | ✅ all |
| **x/y label** | `plot.setLabel('bottom'/'left', t)` | `ax.set_xlabel/ylabel` | `layout.xaxis/yaxis.title.text` | ✅ all |
| **scale: log** | ⚠ `setLogMode` does **not** transform qtviz's bare items — needs data pre-transform (§10) | `ax.set_xscale('log')` | `xaxis.type='log'` | ◑ mpl/web native; pyqtgraph via §10 |
| **scale: symlog** | ❌ no native symlog | `set_xscale('symlog')` | ❌ (log only) | ◑ mpl only → gate |
| **scale: logit** | ❌ | `set_xscale('logit')` | ❌ | ◑ mpl only → gate |
| **scale: time** | `DateAxisItem` on axis | native date units | `xaxis.type='date'` | ✅ representable; needs data-layer dtype (item #4) |
| **x/y limits** | `setXRange/YRange(padding=0)` | `set_xlim/ylim` | `xaxis.range=[lo,hi]` | ✅ all |
| **invert axis** | `vb.invertX/Y(True)` | `invert_xaxis/yaxis` | `xaxis.autorange='reversed'` | ✅ all |
| **aspect lock** | `vb.setAspectLocked(True, r)` | `ax.set_aspect(r)` | `yaxis.scaleanchor='x'` | ✅ all |
| **legend on/off** | `plot.addLegend()` | `ax.legend()` | `layout.showlegend` | ✅ all (content = item #3) |
| **grid on/off** | `plot.showGrid(...)` | `ax.grid(...)` | `xaxis.showgrid` | ✅ all (theme does it now) |
| **tick_format: si/eng** | custom `AxisItem.tickStrings` | `EngFormatter` | `tickformat` (d3 `~s`) | ◑ all, 3 different mechanisms |
| **tick_format: percent** | custom `tickStrings` | `PercentFormatter` | `tickformat='%'` | ◑ all |
| **tick_format: fixed N** | custom `tickStrings` | `FormatStrFormatter` | `tickformat='.Nf'` | ◑ all |
| **tick_format: datetime** | `DateAxisItem` formats | date formatters | `tickformat` date codes | ◑ all (pairs with time scale) |

**Reading of the matrix:**

- **The core surface (title, labels, log, limits, invert, aspect, legend/grid
  on/off) is ✅ on all three backends** — these are one-line native calls. The seam
  is *high feasibility*.
- **symlog/logit are matplotlib-only** → must be capability-gated (§2.3). This is a
  genuine, permanent backend asymmetry, not a temporary gap, so the
  warn-and-degrade contract is the right design, not a workaround.
- **tick formatting is feasible everywhere but via three different mechanisms**
  (pyqtgraph needs a `tickStrings` override; mpl uses `Formatter` objects; Plotly
  uses d3 format strings). This *validates* keeping the public vocabulary tiny and
  semantic (`si | percent | datetime | fixed:N | auto`) and translating per backend
  — **never** passing a backend-native formatter through the seam (that would
  re-introduce the leaky-abstraction risk the early project evaluations flagged).
- **time scale is representable in the seam now**, but only *rendered* correctly
  once the data layer carries datetime dtype through resolve/accessors/events (the
  webengine translator already bails on datetime, `webengine/_translate.py:172`).
  The seam should *accept* `scale="time"` and gate it until item #4 lands.

---

## 4. Interacting through the surface (the coordinate question)

This is the subtler half of the request — and where the seam earns its keep.

### 4.1 Declarative limits vs. interactive range — precedence

`AxisSpec.lim` (declarative) and `ViewState.x_range` (interactive, captured across
rebuilds) both want to set the visible range. Natural, already-correct precedence:

1. `apply_surface` sets the **initial** range from `AxisSpec.lim` during render.
2. `View._install` then restores a pending `ViewState` *after* render
   (`core/view.py:142-144`), so a user's live pan/zoom **wins** across a rebuild or
   backend swap.

No new machinery — the ordering already in `_install` gives the right answer.
Document the rule; add a test.

### 4.2 The real risk — log scale changes the coordinate space (pyqtgraph)

This is the one place that needs care:

- **pyqtgraph:** `setLogMode(x=True)` makes the `ViewBox` operate in **log₁₀
  space**. `vb.viewRange()` then returns log₁₀ values — so `capture_state`
  (`pyqtgraph/render.py:54-59`) and any `RangeEvent` would emit `-1.0 … 3.0`
  instead of `0.1 … 1000`. Brush/select bounds and `RasterController` viewport math
  would be in log space too.
- **matplotlib:** `get_xlim()` returns **data-space** limits even under
  `set_xscale('log')` — so mpl is already consistent.
- **Plotly:** `xaxis.range` under `type='log'` is expressed in **log₁₀** in the
  layout dict — same hazard as pyqtgraph on the way out, and on event ingest.

**Consequence & design rule:** the surface owns the scale, therefore the surface
must own the **data ⇄ scaled** transform, and **every coordinate that crosses the
seam (ViewState, RangeEvent, SelectEvent bounds, HoverEvent, raster ranges) must be
normalized to data space.** Concretely: when a surface has a log axis, the backend's
`capture_state`/event-emit path applies `10**v` on the way out and `log10(v)` on the
way in. This is a small, localized change but it is *mandatory* — getting it wrong
makes log scale silently corrupt linked brushing and datashader. It is the single
highest-risk item in the whole effort, and the reason the seam must be more than a
config bag: **it is the natural home for coordinate normalization.**

### 4.3 Datashader interaction under non-linear scales

`RasterController` re-aggregates to the viewport in data coords with linear pixel
binning. Log/time axes need log/time binning *and* scale-aware viewport ranges —
that is item #2 on the roadmap (datashader `logx/logy`), **out of scope for the
seam.** The seam's obligation is only to **not silently break** datashader:
recommend `scale != "linear"` + `scale="datashader"` **warns and renders linear**
until item #2 lands. Cheap guard, honest behavior.

### 4.4 Backend-swap fidelity (a free win)

Because scale/label/limits live in the **immutable description** (not in
`ViewState`), they automatically survive `View.set_backend(...)` — the View
re-renders the same root through the new backend (`core/view.py:171-173`). Contrast
with pan/zoom, which must be explicitly captured/restored. So "swap pyqtgraph→mpl
and keep my log axes" works by construction, with one caveat: if the target backend
lacks the scale (symlog→pyqtgraph), §2.3 degradation applies.

---

## 5. Risks & open questions

| # | Risk / question | Severity | Mitigation |
|---|---|---|---|
| R1 | Log-space coordinates leak into events/ViewState/raster on pyqtgraph & Plotly | **High** | Surface owns data⇄scaled normalization (§4.2); conformance test asserts events stay in data space under log |
| R2 | symlog/logit unsupported on 2 of 3 backends | Medium | `Capabilities.scales` + warn-and-fallback (§2.3) |
| R3 | tick-format vocab divergence (d3 vs Formatter vs tickStrings) | Medium | Tiny semantic vocabulary, per-backend translation; no native pass-through |
| R4 | time scale needs data-layer datetime dtype | Medium | Accept `scale="time"` in seam; gate render until item #4 |
| R5 | Datashader + non-linear scale | Medium | Warn-and-render-linear until item #2 |
| Q1 | Reuse `OverlayOptions` vs new `Surface` type? | — | Recommend reuse + add `x`/`y` `AxisSpec` (§2.1) |
| Q2 | Sugar (`node.opts(...)`) now or later? | — | Later; (1) normalize-on-render is enough to ship |
| Q3 | Per-element `label` for multi-series legends? | — | Defer to item #3 (legends); seam only does legend on/off |

None of these is a blocker; R1 is the one that must be done *with* log scale, not
after.

---

## 6. Phased plan (de-risk by wiring the dead fields first)

Each phase is independently shippable and headless-testable.

- **Phase A — prove the seam (no new public API). ✅ Landed.** Added
  `surface_of(node)` (`core/compose.py`) + an `apply_surface(...)` step on all three
  backends (`backends/*/_surface.py`, webengine folded into `plotly_layout`), wiring
  the **previously-dead** `OverlayOptions.title / x_label / y_label`. Covered by
  `tests/qtviz/test_surface.py` (8 tests, incl. a regression that the Plotly x/y
  axis `title` dicts are independent). **Scope note:** the `legend` on/off toggle was
  *deferred* out of Phase A — the auto-legend is generated *inside* element renderers
  and means different things per backend (categorical legend vs. colorbar vs. Plotly
  trace legend), so it belongs with the legends milestone (item #3), not the seam.
- **Phase B — log scale.** Add `AxisSpec.scale ∈ {linear, log}`,
  `Capabilities.scales`, warn-fallback, **and R1 coordinate normalization** (the
  hard part). Unblocks the datashader `logx/logy` follow-on.
- **Phase C — declarative limits / invert / aspect.** Cheap per backend; codify the
  §4.1 precedence vs `ViewState`.
- **Phase D — tick-format vocabulary.** `si | percent | fixed:N | auto`; translate
  per backend.
- **Deferred (separate items, named here for sequencing):** `time` scale + datetime
  dtype (#4); datashader under non-linear scales (#2); twin/secondary axes (#6);
  symlog/logit (land opportunistically behind R2 gating).

## 7. Effort & testing

- **Surface area is small and localized:** one new `Immutable` (`AxisSpec`), an
  extended `OverlayOptions`, one new function per backend, one core normalizer, plus
  R1 coordinate handling. No change to `Element`, negotiation, the resolve pipeline,
  or the event vocabulary.
- **Testable offscreen**, matching the existing ~330-test approach (offscreen Qt):
  the backend conformance suite can assert `ax.get_xscale()`/`get_xlabel()`,
  `plot.getAxis('bottom').labelText` / `plot.ctrl.logXCheck`-equivalent, and the
  Plotly layout dict (`fig['layout']['xaxis']['type']`), with a dedicated R1 test
  that drives a log surface and asserts emitted `RangeEvent.x` is in data space on
  every backend. A `Theme`/surface parity test guards "describe once" across
  backends.

## 8. Verdict

**Proceed.** Feasibility is **high** for the core surface (Phase A–C) and the
design risk is low because:

1. The attachment point (`Overlay.options`) and its semantics are **already
   specified and present** — Phase A is finishing parked work, not greenfield.
2. The apply step is a **sibling of an existing per-surface theming call** at a hook
   point that exists in all three backends — no new pipeline stage.
3. Every core property has a **native primitive on all three backends**; the only
   true asymmetries (symlog/logit) fit the project's existing capability-gated
   warn-and-degrade pattern.

The one item demanding real care is **R1 — coordinate normalization under log scale
on pyqtgraph/Plotly.** It is the architectural reason the seam should *own* the data
⇄ scaled transform, and it must be built *together with* log scale (Phase B), never
bolted on after. Start with **Phase A** to wire the dead `OverlayOptions` fields and
de-risk the seam end-to-end before introducing scales.

---

## 9. Phase A — value review (retrospective)

Written after Phase A landed (`surface_of` + `apply_surface`, wiring
`OverlayOptions.title / x_label / y_label` on all three backends;
`tests/qtviz/test_surface.py`). A candid read of what it is and isn't worth, so the
seam isn't mistaken for a finished feature.

**Verdict: low direct value, high strategic value.** On its own, Phase A is a small
correctness fix — axis labels are table stakes, not a feature. Its real worth is as
the *enabling seam* for the high-value work (log/datetime scales, limits, tick
formatting). Framed as a feature it would oversell; framed as "foundation + a silent
bug we shouldn't have shipped," it's honest.

### Where it delivers real value
- **Unblocks the export/reporting wedge.** qtviz's pitch is "interact natively, then
  export publication-quality via matplotlib" — and an unlabeled chart is **not
  publishable**. Before Phase A, `OverlayOptions(title=…, x_label=…)` was *silently
  ignored*; the only way to label an exported figure was to drop to the backend. A
  real, concrete workflow that was broken and now works.
- **Fixes a trust-eroding silent failure.** The API accepted `title=`/`x_label=` and
  did nothing. Silent no-ops are worse than missing features — they make users doubt
  the whole declarative layer. Closing that is worth more than the diff size suggests.
- **Reinforces "describe once, render anywhere."** The same `Overlay(options=…)` now
  yields matching title/labels on pyqtgraph, matplotlib, and webengine.
- **De-risked the seam cheaply.** The hook point now exists in all three backends, the
  `Overlay.options` attachment is proven end-to-end, and a latent Plotly
  shared-`title`-dict bug was caught up front. Phases B–D plug into a validated socket.

### Where it delivers little or no value (the lack thereof)
- **Closes zero competitive gaps** from `matplotlib-capability-review.md`. Log scales,
  datetime, twin axes, reference lines — all still missing. Phase A is the prerequisite
  *under* the high-value list, not on it.
- **Ergonomics mute the win.** Titling a single scatter requires
  `Overlay([scatter], options=OverlayOptions(title="…"))`; there is no `.opts()` /
  `.relabel()` sugar (deferred, §2.2) and a bare `Element` still can't carry a label.
  Many users won't find the capability through that verbosity.
- **`OverlayOptions` is still half-dead.** `legend` and `background` remain unwired, and
  **figure-level `LayoutOptions.title` is still ignored** — so "title a dashboard" still
  silently fails at the `Layout` level. The fix is partial.
- **No new expressive power.** It renders text that was always expressible; it doesn't
  let a user say anything they couldn't already say — they just couldn't *see* it.

### Honest framing & what converts latent → realized value
Phase A is **enabling infrastructure with a bug fix riding along.** Its value is
*latent* — realized only when B/C/D land on the seam. If work stopped here, you'd have
correctly-labelled plots and an unused hook. The case for doing it first is strong
(de-risk the seam, fix a silent failure cheaply); the case for shipping it as a
user-facing win is weak in isolation. In rough leverage order, what realizes the value:

1. **Phase B (log scale)** — the first capability the seam exists *for*, and the top gap
   from the capability review.
2. **A thin `.opts(title=…, x_scale=…)` sugar** — so the seam is reachable without
   `Overlay`-wrapping (§2.2 option 2).
3. **Finish the dead fields** — `legend`, `background`, and `LayoutOptions.title` — so
   the surface contract is no longer partial.

---

## 10. Phase B spike — log scale (findings)

A focused spike (run against the installed pyqtgraph / matplotlib) to resolve the
pivotal unknown before committing to Phase B. **Outcome: log scale is feasible on
all three backends; the work is bounded and concentrated in pyqtgraph.**

### 10.1 Correction to the §3 matrix

The §3 row claiming pyqtgraph log is `plot.setLogMode(x,y)` ✅ is **wrong** and has
been struck. Verified empirically: `setLogMode` only transforms items that
implement `setLogMode`, and qtviz's renderers use **bare** `ScatterPlotItem` /
`PlotCurveItem` / `BarGraphItem` / `ImageItem` — none of which do. The axis switches
to log ticks but the data stays linear → broken render on the default backend.

### 10.2 Per-backend findings

- **matplotlib — trivial, no R1.** `ax.set_xscale("log")` transforms the data, and
  `ax.get_xlim()` returns **data-space** limits under log (spike: `~0.7..1412` for
  data `1..1000`). So `connect_range` (reads `get_xlim`) and the data-space
  `selectables` are already correct — **matplotlib needs no coordinate
  normalization.** It also gets `symlog` / `logit` for free.
- **webengine (Plotly) — small, R1 in one place.** `xaxis.type="log"` renders
  correctly, but `xaxis.range` in `relayout`/`restore` is **log₁₀**. R1 lives in
  `_translate.parse_relayout` (incoming) and `restore_state` (outgoing). Test is
  display-gated (offscreen QWebEngine is skipped), so the figure-dict (`type=='log'`)
  is unit-testable but the range round-trip is not headless.
- **pyqtgraph — the bulk, but proven.** `setLogMode` is out (10.1). **Approach A
  works** (spike-verified): pre-`log10` the plotted data in the renderers **and** set
  `AxisItem.setLogMode(True)` for tick labels only. Result was correct — view range
  in exponent space (`~0..3`) and tick labels `1 / 10¹ / 10² / 10³`. Because the data
  is now in exponent space, *everything downstream* (viewRange, range/tap events,
  picks, brush) is in exponent space too, so a single consistent `10**v` de-log at
  each emit boundary restores data space.

### 10.3 The R1 normalization map (pyqtgraph only)

Every boundary where a (possibly-log) coordinate crosses the seam, with the fix:

| Boundary | Site | Normalization |
|---|---|---|
| capture_state | `pyqtgraph/render.py:54-59` | `viewRange` → `10**` for log axes |
| restore_state | `pyqtgraph/render.py:61-68` | `log10(range)` before `setXRange/YRange` |
| RangeEvent | `_interaction.py:53` (`_on_range`) | `viewRange` → `10**` |
| brush / SelectEvent | `_interaction.py:43,64` | store selectables as `log10` so the mask runs in exponent space; de-log the emitted `bounds` |
| TapEvent | `_interaction.py:75` | `mapSceneToView` → `10**` |
| pick / hover | `_events.py:20-32` (`wire_scatter`) | `sp.pos()` → `10**` |

All keyed off per-axis `x_log` / `y_log` flags parked on the `QtvizViewBox` (+ read
by the handle). matplotlib and the webengine native path need **none** of this row.

### 10.4 Threading the scale to the renderers

`RenderContext` gains `x_scale` / `y_scale` (resolved once in `_render_cell` from
`surface_of(node)` + a capability check). The renderers that plot x/y data —
`scatter`, `curve`, `bars`, `errorbars`, `spread` — apply a `_logify(arr, is_log)`
helper. `Image` / `Heatmap` under a log axis is unusual; **defer + gate** rather than
transform a raster.

### 10.5 Edge cases & policy

- **Non-positive values under log** → `log10` yields `nan`/`-inf` (spike confirmed).
  **Policy: drop non-finite points with a one-time `warnings.warn`,** matching
  matplotlib's masking behavior. Maskable cleanly (`np.isfinite`).
- **Datashader + non-linear scale** — out of scope (roadmap item #2). **Gate:** warn
  and render linear when `scale != "linear"` and `scale == "datashader"`.
- **symlog / logit** — matplotlib-only (verified: pyqtgraph #1035 open, Plotly
  log-only). Capability-gate via `Capabilities.scales`; including `symlog` now is
  cheap and *exercises the degradation path* (mpl renders it; pyqtgraph/web warn →
  linear). No R1 impact (mpl limits stay data-space).

### 10.6 Effort & risk

| Backend | Effort | R1 | Risk |
|---|---|---|---|
| matplotlib | ~1-liner + capability + test | none | low |
| webengine | small (`type='log'` + relayout/restore) | one path, display-gated test | low–med (untestable headless) |
| pyqtgraph | bulk: 5 renderers + `RenderContext` + ViewBox/events/handle R1 + masking (~120–150 LOC) | full §10.3 map | medium — bounded, **feasibility now proven** |

### 10.7 Recommendation

Two viable rollouts; the spike makes either safe:

- **All-at-once Phase B (recommended).** Log on all three backends in one phase —
  matplotlib (easy), webengine (small), pyqtgraph (Approach A). Preserves "renders
  identically"; the risk is concentrated in the pyqtgraph R1 map but its feasibility
  is now proven, and TDD against the §10.3 boundaries makes it tractable.
- **Staged B1 → B2 (lower-risk increments).** B1: log on matplotlib + webengine with
  `Capabilities.scales` + warn-fallback, **pyqtgraph temporarily gated to
  `{"linear"}`** (warns). B2: pyqtgraph Approach A, restoring consistency. Smaller
  PRs, but the *default* backend is temporarily linear — a visible (warned) "describe
  once" gap until B2.

**Open sub-decisions for whoever implements:** (1) non-positive policy — *drop + warn*
recommended; (2) include `symlog` now — cheap, exercises gating; (3) datashader gate —
yes. None blocks starting.

---

## Appendix — concrete hook points (for whoever implements)

| Concern | File / line | Change |
|---|---|---|
| Surface config object | `core/options.py:37-54` | extend `OverlayOptions` with `x`/`y` `AxisSpec`, `aspect`; add `AxisSpec` `Immutable` |
| Normalizer | `core/_host.py` / `core/compose.py` | add pure `surface_of(node) -> OverlayOptions` |
| Capabilities | `core/capabilities.py` | add `scales: frozenset[str]` (+ optional `tick_formats`) |
| pyqtgraph apply | `backends/pyqtgraph/render.py:149` (after `style_plot`) | call `apply_surface(plot, surf, theme)`; new `_surface.py` |
| pyqtgraph coords (R1) | `backends/pyqtgraph/render.py:54-68` + events | normalize log ⇄ data in `capture_state`/emit |
| matplotlib apply | `backends/matplotlib/render.py:144` (after `apply_theme_ax`) | call `apply_surface(ax, surf, theme)`; new `_surface.py` |
| webengine apply | `backends/webengine/_figure.py:254` (`plotly_layout`) | thread `surf` into layout; normalize `range` under `type='log'` |
| precedence | `core/view.py:142-144` | confirm ViewState-after-surface ordering; test |
| degradation | per backend `apply_surface` | warn + fallback when `scale`/`tick_format` ∉ `capabilities.scales` |
