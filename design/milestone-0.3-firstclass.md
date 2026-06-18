# Milestone — 0.3 "First-class concepts" (R5)

> The two afterthoughts from the weakness investigation, promoted to real models
> (root cause **R5** in `weakness-root-causes.md`): **axes** (modeled as a cosmetic
> "surface") become a coordinate concept, and **legends** (a side-effect of the
> color-mapping path) become a per-element contract. Decisions: **DP4 / [D56]**
> (axes — this is roadmap **Phase B**, already spiked) and **DP5 / [D55]** (legends),
> refined by **[D59]/[D60]** below.
>
> Axes design is fully worked in `axis-surface-feasibility.md` (§2 AxisSpec, §4/§10
> the R1 coordinate rule, Appendix the hook points) — this milestone references it
> rather than repeating it. Legends build on `milestone-color-encoding.md` ([D23]
> deferred "legend-as-first-class").

## 0. Goal & scope

**Goal.** A developer can say `scale="log"`, set axis limits, invert an axis, and get
a **legend on any multi-series plot** — once, rendered consistently across pyqtgraph,
matplotlib, and webengine.

**In scope.**
- **Axes (DP4):** `AxisSpec` (`scale ∈ {linear, log, symlog}`, `lim`, `invert`) +
  `aspect`; `Capabilities.scales` + warn-fallback; the **R1 coordinate normalization**
  (the hard part); `_logify` in the x/y renderers. *(= feasibility Phases B + C.)*
- **Legends (DP5):** a per-element `legend_entry()` contract + Overlay aggregation;
  wire the dead `OverlayOptions.legend` (+ position); webengine legends; a true
  pyqtgraph gradient colorbar.

**Deferred / non-goals (this milestone).** `tick_format` vocabulary (feasibility
Phase D); `scale="time"` / datetime (blocked on the data layer carrying datetime
dtype); datashader `logx`/`logy` (roadmap item #2 — the seam only **guards** it, §1.5);
twin/secondary axes; the figure-level `LayoutOptions.title`; a `Legend` *element* you
place (the *contract* is enough for 0.3 — a placeable node can follow).

---

## 1. Axes (DP4 / [D56] — feasibility Phase B + C)

### 1.1 The shape
- **`AxisSpec`** (new `Immutable`, hashable): `label`, `scale`, `lim`, `invert`
  (`tick_format` field reserved, honored "auto" only this milestone).
- **`OverlayOptions`** gains `x: AxisSpec`, `y: AxisSpec`, `aspect: float | None`;
  `x_label`/`y_label` become conveniences populating `x.label`/`y.label` (back-compat).
- Attaches via the existing `surface_of(node)` normalizer + per-backend `apply_surface`
  (Phase A's seam) — no `Element` change, no new pipeline stage (feasibility §2.2).

### 1.2 Capability-gated scales
`Capabilities.scales: frozenset[str]` — pyqtgraph `{linear, log}`, matplotlib
`{linear, log, symlog, logit}`, webengine `{linear, log}`. A surface requesting a
scale a backend lacks **warns and falls back to linear** (house pattern, feasibility
§2.3). `symlog` is included precisely because it *exercises* this gate (mpl renders;
pyqtgraph/web warn → linear).

### 1.3 R1 — coordinate normalization (the load-bearing part)
Log changes the coordinate space on **pyqtgraph** (pre-`log10` the data + `AxisItem.
setLogMode` for ticks → ViewBox in exponent space) and on **webengine** (`xaxis.range`
is log₁₀). Every coordinate crossing the seam must be normalized to **data space**:
`capture/restore_state`, `RangeEvent`, `SelectEvent` bounds, `TapEvent`, pick/hover,
raster ranges. The exact site→fix table is `axis-surface-feasibility.md` §10.3; keyed
off per-axis `x_log`/`y_log` flags on `QtvizViewBox`. **matplotlib needs none**
(`get_xlim` stays data-space under log). This is the single highest-risk item — built
*with* log, never bolted on after.

### 1.4 Threading
`RenderContext` gains `x_scale`/`y_scale` (resolved once in `_render_cell` from
`surface_of(node)` + the capability check). The x/y renderers (`scatter`, `curve`,
`bars`, `errorbars`, `spread`) apply `_logify(arr, is_log)`. `Image`/`Heatmap` under a
log axis: **defer + gate** (don't transform a raster).

### 1.5 Edge policy ([D59])
- **Non-positive under log** → drop non-finite points with a one-time `warnings.warn`
  (`QtvizWarning`), matching matplotlib's masking.
- **datashader + non-linear scale** → warn and render linear (item #2 not in scope).
- **Limits precedence:** `AxisSpec.lim` sets the initial range; a live `ViewState`
  restored in `View._install` *after* render wins across rebuilds (feasibility §4.1).
  No new machinery — document + test the ordering.

### 1.6 Rollout ([D59]) — all-at-once
Log on all three backends in one go (mpl easy, webengine small, pyqtgraph Approach A),
**preserving "renders identically"** over the staged B1→B2 alternative that would
leave the default backend temporarily linear. Feasibility-proven; TDD against the
§10.3 boundaries makes the pyqtgraph R1 map tractable (~120–150 LOC, bounded).

---

## 2. Legends (DP5 / [D55])

### 2.1 The move — legend as a per-element contract, not a color-mapping side-effect
Today a `Legend` is only what `map_colors` *returns* (so only `color_by`-Scatter and
rasters get one). Add a small contract so **every element contributes**, and an Overlay
aggregates them:

- **`Element.legend_entry(theme) -> LegendEntry | None`** — the element's swatch + label
  for a multi-series legend (a single-color `Curve`/`Bars`/`Histogram`/`ErrorBars`/
  `Spread`/static `Scatter`). Returns `None` when the element shouldn't contribute
  (e.g. a `color_by` Scatter, which already emits its own categorical/continuous
  `Legend`). Default base implementation; elements override as needed.
- **`label: str | None`** field on the styling elements (the legend text; `None` →
  omit or a sensible default). Replaces the role the dead `Options.label` never filled.
- **Overlay aggregation** — after a backend renders an Overlay's children, it builds one
  legend from the children's `legend_entry()` results, drawn via the existing
  `add_legend`/`_add_legend` path.

### 2.2 Wire the dead surface fields
- **`OverlayOptions.legend: bool`** (currently unread) → consulted by `apply_surface`
  to show/hide; add `legend_position` (a small vocabulary: `auto|right|top|none`,
  translated per backend).
- This is the "legend on/off toggle" Phase A explicitly deferred to "the legends
  milestone" (feasibility §6) — it lands here.

### 2.3 Backend parity
- **webengine** — flip the hardcoded `showlegend: False` (`_figure.py:293`); per-trace
  `name` is already set; emit a Plotly `colorbar` from the currently-discarded
  `_legend` (`_figure.py:74`). Closes the "webengine renders no legends" gap.
- **pyqtgraph** — replace the 5-stop stepped swatch with a true `pg.ColorBarItem`/
  `GradientLegend` gradient (the dep ships both); matplotlib already does a real
  gradient (`figure.colorbar`). Closes the native colorbar-parity gap.

### 2.4 Legend honesty
Reuse the [D48] rule already in encoding: categorical → key; continuous linear →
colorbar with truthful `vmin/vmax`; `eq_hist` density → endpoints-only. The
multi-series legend (2.1) is a categorical key of element labels.

---

## 3. Discussion items (recommended; confirm at review)

### [D59] Axes 0.3 scope, rollout & edge policy
Scope = feasibility **Phases B + C** (`log`, `symlog`-gated, `lim`, `invert`,
`aspect`); **defer** tick-format vocabulary (Phase D) and `time`/datetime (data
layer). **Rollout = all-at-once** log across all three backends (preserve "renders
identically"). Edge policy: non-positive-under-log → **drop + warn**; datashader +
non-linear → **warn + linear**; `lim` initial, live `ViewState` wins. `Capabilities.
scales` + warn-fallback; `symlog` included to exercise the gate.
*Alternatives weighed:* staged B1→B2 (smaller PRs, but the default backend is
temporarily linear — rejected for the consistency cost); per-element axis field
(rejected, feasibility §2.2).

### [D60] Legend as a per-element contract (realizes [D23]'s deferral)
A `legend_entry()` contract + a `label` element field + Overlay aggregation, rather
than (a) keeping legends a color-mapping side-effect (the status quo — no multi-series
legends) or (b) a full first-class `Legend` *element* now (deferred — the contract
covers the 0.3 need; a placeable node can follow). Wire `OverlayOptions.legend` +
`legend_position`; webengine legends on; pyqtgraph gradient colorbar.

---

## 4. Test plan (TDD — write first)

**Tier-1 (pure):** `AxisSpec` immutability/equality; `surface_of` carries axis config;
`capabilities.scales` gating logic; `_logify` masks non-finite + warns once;
`legend_entry()` returns the right label/swatch (and `None` for `color_by`).

**Tier-2 (offscreen, both native backends):**
- scale: `ax.get_xscale()=="log"` (mpl); pyqtgraph `AxisItem` log mode + data
  pre-transformed; warn-fallback when a backend lacks a scale.
- **R1 (the critical test):** drive a log surface and assert emitted `RangeEvent.x` /
  `SelectEvent.bounds` / hover are in **data space** on pyqtgraph (and mpl); a
  capture→restore round-trip preserves data-space ranges under log.
- limits/invert/aspect applied; `ViewState` (pan/zoom) wins over `lim` after rebuild.
- legends: a two-`Curve` Overlay with labels draws one legend with both entries on
  both backends; `OverlayOptions.legend=False` suppresses it; a `color_by` Scatter
  still emits its own legend (no double legend); pyqtgraph continuous draws a gradient.
- datashader + `scale="log"` warns and renders linear (no crash).

**Tier-3 (webengine, display-gated):** figure dict `xaxis.type=="log"`; `showlegend`
true with per-trace names + a colorbar.

## 5. Benchmarks (per cadence)
- `_logify` per-render cost on a 1M-point Scatter (should be one vectorized `log10` +
  `isfinite` mask — measure it's a small fraction of render).
- R1 normalization per event (must stay microsecond-scale — it's on the event path).
`benchmark`-marked, like `test_bench_degrade.py`.

## 6. Phased increments (review at each boundary)
1. **AxisSpec + surface plumbing** — `AxisSpec`, extend `OverlayOptions`,
   `Capabilities.scales`, thread `x_scale`/`y_scale`; **limits + invert + aspect**
   (no coordinate hazard) + warn-fallback. Green boundary: declarative limits/invert
   work on all backends.
2. **Log scale + R1** — `_logify` in the renderers; the full §10.3 normalization map
   (pyqtgraph) + webengine range R1; non-positive drop+warn; datashader gate; symlog
   gating. The load-bearing increment; TDD the R1 boundaries first.
3. **Legend contract** — `legend_entry()` + `label` + Overlay aggregation; wire
   `OverlayOptions.legend`/`position`.
4. **Legend parity** — webengine legends; pyqtgraph gradient colorbar.

## 7. Risks
| # | Risk | Mitigation |
|---|------|------------|
| 1 | R1 log normalization missed at a boundary → silently corrupts linked brushing/datashader | TDD the §10.3 table first; one R1 test per boundary asserting data-space output |
| 2 | pyqtgraph log touches many sites (5 renderers + events + handle) | bounded ~120–150 LOC, feasibility-proven; increment 2 is log-only |
| 3 | Double legends (a `color_by` Scatter in a labeled Overlay) | `legend_entry()` returns `None` for `color_by`; test for single legend |
| 4 | webengine legend/colorbar untestable headless | unit-test the figure dict; display-gated render test |
| 5 | `label` field touches all elements | small additive field; default `None`; covered by the conformance + legend tests |

## 8. Acceptance
A `Curve(…, label="raw") * Curve(…, label="smoothed")` wrapped in
`Overlay(options=OverlayOptions(title=…, x=AxisSpec(scale="log"), legend=True))`
renders on **pyqtgraph and matplotlib** with: a log x-axis (data correctly
transformed), a two-entry legend, and — critically — a brush/zoom that emits
**data-space** coordinates (not log space). Switching `backend="webengine"` keeps the
log axis + legend. `symlog` warns→linear on pyqtgraph/web, renders on mpl. Suite green;
ruff clean; benchmarks within ceilings.
