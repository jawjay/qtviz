# Milestone — 0.4 "Vocabulary, annotation & export" (R2/R3 partial, R6)

> The demand-proven vocabulary growth [D54] plus the composite-export edge [D57]
> from the post-0.1 plan, extended per `improvement-plan.md` [D61] (owner-approved
> 2026-07-24) with the annotation/reference layer — the gallery's most hand-rolled
> pattern — and color normalization. The element vocabulary stays **curated**
> ([D54]: the public registry remains parked); everything here is additive.
> New decisions below: [D67]–[D72].

## 0. Goal & scope

**Goal.** A developer can drop reference lines/bands/text onto any plot, draw the
statistical staples (box/violin/grouped/stacked), aggregate a Heatmap honestly,
map colors through a non-linear norm, and export a mixed-backend layout as one
image — on all three backends, honor-or-warn intact.

**In scope.**
- **Annotation/reference elements ([D70], realizes [D61]):** `HLine` / `VLine` /
  `Span` / `Text` — pure-data, data-less elements, composable via `*`.
- **Bars growth ([D68]):** `group` honored at last — `mode="grouped"|"stacked"`.
- **Heatmap.aggregator ([D69]):** real reduction (`mean|sum|max|min|count|last`),
  closing the two "last value wins" TODOs.
- **BoxPlot + Violin ([D67]):** shared, backend-identical statistics.
- **Color normalization ([D71]):** `color_norm="linear"|"log"` on `color_by`.
- **Composite export + knobs ([D72]):** `CompositeRenderHandle.export("png")`
  stops raising; `dpi`/`transparent` knobs where the engine supports them.

**Deferred / non-goals.** Public element registry ([D54] parked); contour/quiver
(demand-gated); diverging/discrete norms (follow [D71] when needed); single
*vector* export across backends (intrinsic, [D58]); arrows/leader-lines on `Text`;
twin axes (0.5 scoping decision, per `improvement-plan.md`).

---

## 1. Annotation & reference elements ([D70])

Four new curated elements, **data-less** (no `DataRef` — precedent: `RawFigure`
passes through resolve untouched). Immutable, value-hashed, composable via `*`;
each carries `label` and participates in `legend_entry()` (a labeled threshold
line belongs in the legend).

| Element | Fields | pyqtgraph | matplotlib | webengine (Plotly) |
|---|---|---|---|---|
| `HLine(y)` | `y, color, line_width, line_style, alpha, label` | `InfiniteLine(angle=0)` | `axhline` | `layout.shapes` line |
| `VLine(x)` | `x, …same…` | `InfiniteLine(angle=90)` | `axvline` | `layout.shapes` line |
| `Span(lo, hi, orient)` | `lo, hi, orient="h"|"v", color, alpha, label` | `LinearRegionItem` (non-interactive) | `axhspan`/`axvspan` | `layout.shapes` rect |
| `Text(x, y, text)` | `x, y, text, color, size, anchor, label=None` | `pg.TextItem` | `ax.text` | `layout.annotations` |

- **webengine shape routing:** Plotly shapes/annotations are *layout*-level, not
  traces. `_figure.build` collects annotation elements into `layout.shapes` /
  `layout.annotations`; they contribute **no trace** (and no source-id row — they
  emit no events, on any backend). Span/line coordinates use axis refs (`xref="x"`,
  `yref="y"`; full-length lines use `xref="paper"` 0→1 on the free axis).
- **Log interaction (R1):** on pyqtgraph the positions logify like data
  (`HLine(y=…)` under log-y sits at `log10(y)`); non-positive under log → the
  standard drop-and-warn. matplotlib/webengine need nothing (native log axes).
- **Honor-or-warn:** styling fields are RECOMMENDED and honored on all three
  (line_style on webengine shapes via `dash`); `Span` on pyqtgraph uses a
  `LinearRegionItem` with `movable=False` — interactivity via `handle.native()`.

## 2. Grouped / stacked Bars ([D68])

`Bars` gains `mode: Literal["grouped", "stacked"] = "grouped"` (meaningful only
with `group=`). `group` names a column: each distinct value becomes one series —
palette-colored in category order (`category_swatches`, same rule as `color_by`)
with **one legend entry per group** through the [D60] aggregation path.

- Shared pure helper `core/_stats.group_bars(x, y, groups)` → per-group aligned
  arrays (missing combinations → 0), so all three backends draw identical data.
- pyqtgraph: one `BarGraphItem` per group (grouped: sub-width offsets; stacked:
  `y0` bases). matplotlib: offset `ax.bar` / `bottom=`. webengine: one trace per
  group + `layout.barmode`.
- `group` moves into HONORED on all three; `orient="h"` with `group` stays
  warn-degraded (deferred — the transposed layout math isn't worth it yet).
- `Bars.color` with `group` set → ValidationError (mutually exclusive, same
  pattern as `color`/`color_by`).

## 3. Heatmap.aggregator ([D69])

`Heatmap.aggregator: Literal["last", "mean", "sum", "max", "min", "count"]`
(default `"mean"` — **breaking-ish**: the old implicit behavior was `"last"`,
which stays available; the old default was undocumented and warned since 0.2, so
the honest default wins). Shared pure helper `core/_stats.grid_reduce(x_codes,
y_codes, values, shape, agg)` (bincount-based, vectorized) replaces the three
copies of "last value wins"; all backends render the identical grid. `aggregator`
moves into HONORED everywhere; the §5.5 TODOs close.

## 4. BoxPlot + Violin ([D67])

Two new elements sharing one stats core so every backend draws the *same*
numbers ("one Element, one meaning" — never each engine's house statistics):

- `BoxPlot(data, column=…, by=None, color=…, label=…)` — one box, or one per
  category of `by`. `core/_stats.box_stats(values)` → median, q1/q3 (linear
  interpolation), whiskers at 1.5·IQR clipped to data, outliers beyond.
  pyqtgraph: drawn from primitives (rect + lines + outlier scatter); matplotlib:
  `ax.bxp(precomputed, showfliers=True)`; webengine: Plotly box trace with
  **precomputed** q1/median/q3/fences (Plotly supports them) + outlier points.
- `Violin(data, column=…, by=None, …)` — `core/_stats.kde(values)` (Gaussian,
  Scott's rule, 128-point grid) → a symmetric polygon. pyqtgraph: filled
  `PlotDataItem` polygon; matplotlib: `fill_betweenx`; webengine: a filled
  scatter polygon (`fill="toself"`) — **not** Plotly's violin trace, whose own
  KDE would diverge from the native backends.
- Both: `by` categories share x-positions 0..n-1 with category tick labels;
  palette-colored per category when `by` is set (+ legend entries).

## 5. Color normalization ([D71])

`Scatter.color_norm: Literal["linear", "log"] = "linear"` (with `color_by`,
numeric only; validated). `map_colors(..., norm="log")` normalizes through
`log10` before the LUT. **Legend honesty ([D48]):** a log-normed colorbar is
non-linear in value, so the emitted `Legend` sets `linear=False` → endpoints-only
key on every backend (never a gradient bar implying linear ticks); webengine gets
`colorbar` ticks at log-spaced values via `cmin/cmax` on the log10'd data…
deferred — webengine log-norm renders the same endpoints-honest way (css list).
Non-positive values under a log norm: drop-and-warn, same policy as axes.

## 6. Composite export + knobs ([D72])

- `CompositeRenderHandle.export("png", path)` stops raising: the Qt container
  (all panes, chrome included) is grabbed via `QWidget.grab()` → one raster.
  Honest edges: `svg`/`pdf` still raise (single vector surface is a non-goal,
  [D58]); a webengine pane needs a live compositor — offscreen it grabs blank,
  so the render test is display-gated (unit test covers the wiring).
- Knobs: `export(fmt, path, *, dpi=None, transparent=False)` — honored by
  matplotlib (`savefig`); pyqtgraph honors `transparent` (background) and warns
  on `dpi`; webengine warns on both (honor-or-warn, [D51]).

---

## 7. Test plan (TDD — write first)

**Tier-1 (pure):** element immutability/validation (annotation fields, Bars
group×color exclusivity, aggregator/norm vocabularies); `box_stats` against
numpy percentile ground truth; `kde` integrates to ~1; `grid_reduce` per-agg
correctness incl. empty cells; `group_bars` alignment with missing combos;
`map_colors(norm="log")` → `linear=False` legend + correct LUT indices;
webengine figure specs (shapes/annotations routing, barmode, precomputed box
values, no source-id rows for annotations).

**Tier-2 (offscreen, both native backends):** each annotation element renders +
appears in the natives map + labeled ones join the legend; HLine under log-y
sits at the logified position (R1); grouped/stacked bars item counts + stacked
bases; Heatmap aggregation visible in the rendered grid; box/violin render with
`by` categories; log-norm scatter draws and emits an endpoints-only legend;
composite export writes a non-empty png for a mixed native layout; export knobs
honored-or-warn per backend.

## 8. Benchmarks (per cadence)
`grid_reduce` on 1M points (vectorized bincount — ms-scale); `box_stats`/`kde`
on 100k values (ms-scale). `benchmark`-marked, in `test_bench_stats.py`.

## 9. Phased increments (review at each boundary)
1. **Annotation/reference elements** — the four elements on all three backends,
   legend + log (R1) interplay included.
2. **Bars grouped/stacked + Heatmap.aggregator** — the shared `_stats` helpers
   land here.
3. **BoxPlot + Violin** — stats core + three renderers each.
4. **Color norm ([D71])** — encoding + honest legend.
5. **Composite export + knobs ([D72])** — the [D57] edge.

## 10. Risks
| # | Risk | Mitigation |
|---|---|---|
| 1 | Annotation elements tempt scope creep (arrows, callouts, drag) | curated cut of 4; interactivity stays behind `handle.native()` |
| 2 | Plotly's own box/violin stats diverge from numpy's | precompute and pass values; violin drawn as a polygon, never Plotly's KDE |
| 3 | Aggregator default change (`last`→`mean`) surprises 0.3 users | CHANGELOG-called-out; `"last"` kept; the old path warned as unhonored since 0.2 |
| 4 | Composite grab captures a blank webengine pane offscreen | documented; display-gated render test; per-pane `to_png` remains |
| 5 | 5 increments of surface growth erode "hold it in your head" | everything additive + curated; README table updated once at release |

## 11. Acceptance
The telemetry example rebuilt with `HLine`/`Span` reference elements instead of
hand-rolled tolerance bands; a `BoxPlot(by=)` + grouped `Bars` dashboard renders
identically on pyqtgraph and matplotlib (webengine spec verified headless); a
`Heatmap(aggregator="mean")` draws true means; a log-normed `color_by` shows an
endpoints-only key; a mixed pyqtgraph+matplotlib `Layout` exports one PNG.
Suite green; ruff clean; benchmarks within ceilings.
