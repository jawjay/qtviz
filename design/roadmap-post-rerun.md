# Post-re-audit roadmap — the closure waves (1.4 → 2.0-gate)

> **Input.** The gallery re-audit
> ([`matplotlib-gallery-audit-rerun.md`](matplotlib-gallery-audit-rerun.md),
> commit `22b3d34`) measured the wave 1–3 vocabulary against all 507
> examples: in-scope achievability 47% → 60%, core chart categories
> 57% → 73%, 56 up-flips, none down. What remains is qualitatively
> different from what the first roadmap faced: the ❌ mass is no longer
> scattered vocabulary but (a) a short list of **named warts and residue**
> the re-audit itself produced, and (b) **parked subsystems** (polar,
> triangulation, insets, the mpl toolkits, styling zoos) that are gaps by
> decision, not by omission.
>
> **Strategic read — the gallery metric is exhausted.** Waves 1–3 bought
> 56 flips with ~15 vocabulary items because the gaps clustered. The
> remaining flips come one or two at a time, each costing a subsystem or a
> niche element. From here, gallery count stops being the planning signal;
> items below are priced by **user value and architectural fit**, with the
> expected flips noted only as a side effect. This document schedules the
> profitable tail and states explicitly where we stop.
>
> Decisions are numbered **[D111]–[D120]**, house style: recommendations to
> confirm at review, alternatives recorded. Cadence unchanged: spec →
> discussion items → TDD increments → green commits; **direction confirmed
> at each release boundary** — this plan is a proposal, not a commitment
> arc.

## 0. Architectural read (what the remaining work has in common)

1. **Everything scheduled below rides existing seams.** No item requires a
   new core contract: [D105]'s normalize/denormalize pipeline absorbs the
   norm tail; [D107]'s `core/_geometry.py` arrow-head math is reused by
   three items (quiver key, errorbar limit arrows, streamline heads);
   [D98]'s label-format vocabulary absorbs cell labels; the [D70]
   annotation class absorbs contour labels. The plan is deliberately
   *reuse-shaped* — if an item turns out to need a new seam, that is a
   signal to re-park it and bring the finding to review.
2. **"Compute in core, draw everywhere" ([D67]/[D110]) remains the default.**
   Streamline integration, contour-label placement, cell-label contrast,
   symlog/boundary normalization — each is one numpy implementation feeding
   all three backends, tested bit-identical in core, drawn as primitives
   (polylines, text, colors) the renderers already have.
3. **The one genuine architecture question left is polar ([D119]).** It is
   the only remaining *projection*, it blocks ~11 examples plus radar
   charts (a real user ask, not just gallery bait), and it interacts with
   R1 (events/state are rectilinear tuples). It gets a decision spike with
   a go/no-go gate, not a scheduled implementation.
4. **Quality debt rides ahead of vocabulary.** The datashader autorange
   drift bug (open, user-visible) and the docs debt (README/quickstart
   barely show the wave 1–3 vocabulary; example 35 predates it) are
   scheduled *before* new elements — shipping capability nobody can
   discover, on top of a drifting raster, is the wrong order.

## 1. Release map

| Release | Theme | Items | Expected flips (≈) |
|---|---|---|---|
| **1.4 — Finish & honesty** | fix what the re-audit named; make shipped work discoverable | [D111] Mesh edge validation · [D112] quiver key · [D113] heatmap cell labels · [D114] symlog/boundary norms · [D115] `Stem` · [D116] errorbar limit arrows · [D120] docs/example debt · datashader drift bug (P2, first) | ~10 |
| **1.5 — Fields & flow** | complete the 2-D field story opened by wave 3 | [D117] contour inline labels · [D118] `Streamlines` | ~4 |
| **2.0-gate — Polar spike** | the last projection: decide, don't drift into it | [D119] polar feasibility spike → go/no-go review | ~11 if go |
| **Parked register** | unchanged except graduations noted in §6 | — | — |

## 2. Wave 1.4 — finish & honesty

### P2 bug (before any vocabulary): datashader autorange drift
Datashaded views zoom out over time (see memory/known-bugs; screenshots
work around it with a short settle). Suspected feedback loop: each
re-aggregation writes a raster whose bounds feed autorange, which triggers
re-aggregation. Fix shape: the raster item must not participate in
autorange after the first aggregation (mpl: exclude from `dataLim` — the
[D95]-selector fix is precedent; pg: `ItemIgnoresTransformations`-style
opt-out via `setAutoRangeEnabled`/bounds override on the ImageItem).
Acceptance: a streaming datashaded view holds its viewport for 60s of
appends under the offscreen harness. **Effort: M (diagnosis is most of
it).**

### [D111] `Mesh` edge validation (re-audit wart #1)
- **Change.** `Mesh.__init__` validates edges: 1-D, strictly monotonic,
  `len(x_edges) == ncols+1`, `len(y_edges) == nrows+1`. 2-D edge arrays
  raise `ValidationError("Mesh edges must be 1-D (rectilinear); curvilinear
  meshes are not supported — see design/roadmap-post-rerun.md §6")` instead
  of today's raw numpy `TypeError`.
- **Tests.** 2-D edges, reversed edges, off-by-one lengths → three clear
  messages. **Effort: S.**

### [D112] Quiver reference key (re-audit wart #2)
- **API.** `Quiver(..., key: float | None = None, key_label: str | None =
  None)` — e.g. `key=10, key_label="10 m/s"`. Emits a **legend entry whose
  sample glyph is an arrow of the stated magnitude** rendered at the same
  scale as the field.
- **Recommendation: legend-based, not corner-anchored.** mpl's `quiverkey`
  pins to axes-fraction coordinates, which qtviz does not model (parked —
  figure-space chrome). The legend seam already exists on all three
  backends and is where users look for "what does an arrow mean".
  mpl: custom legend handler drawing a `FancyArrow` sample; pg: custom
  `ItemSample` painting shaft+head; Plotly: a one-point legend-only trace.
  Core computes the sample geometry from the same [D107] `_geometry`
  scale, so the key is truthful by construction.
- **Alternative rejected:** axes-fraction anchored key — reopens the
  figure-space coordinate gap for one feature.
- Unlocks `quiver_demo` ◑→✅. **Effort: M.**

### [D113] Heatmap cell labels with computed contrast (baseline wart #4)
- **API.** `Heatmap(cell_labels: str | None = None)` accepting the [D98]
  vocabulary (`"auto"` | format-spec). One label per aggregated cell.
- **Core.** The [D105] norm pipeline already maps cell value → RGBA in
  core; add `label_color(rgba) -> theme.foreground | theme.background` by
  WCAG relative luminance (threshold ≈ 0.45, constant chosen by eye against
  the mpl reference figure). Label text, position (cell center), and color
  are computed once; backends draw plain text (mpl `ax.text`, pg
  `TextItem`, Plotly annotations). Cell count guard: warn and skip labels
  above ~400 cells (matches mpl's practical limit; honest, not silent).
- Unlocks `image_annotated_heatmap` ◑→✅; retires the last open baseline
  defect. **Effort: M.**

### [D114] Norm tail — `symlog` and `boundary`
- **API.** `Image`/`Heatmap`/`Mesh` gain `norm="symlog"` (with
  `linthresh: float = 1.0`) and `norm="boundary"` (requires
  `levels: Sequence[float]`, ascending; values bin into `len(levels)-1`
  discrete colors sampled evenly from the colormap).
- **Core.** Two new branches in the [D105] normalize/denormalize pair:
  symlog is the standard piecewise log (mpl's formula, one numpy
  expression each way); boundary is `np.searchsorted` forward and
  bin-midpoint backward. Round-trip property tests like the existing
  linear/log/power ones; grids stay bit-identical across backends.
- **Colorbar honesty ([D48] pattern).** mpl: `BoundaryNorm`-style discrete
  colorbar with level ticks (denormalizing ticks already exists); pg:
  endpoints key (non-linear rule already in place); Plotly: hidden scale
  for non-linear (existing rule).
- Unlocks `colormap_normalizations_symlognorm` ❌→✅,
  `pcolormesh_levels` ◑→✅, `contourf_log` note improves. **Effort: M.**

### [D115] `Stem` element
- **Curation bar ([D54]).** Stem/lollipop plots exist natively in
  matplotlib (`stem`), Plotly (line+marker idiom), pandas/seaborn idiom;
  drawable on all three backends. Passes.
- **API.** `Stem(data, *, x, y, baseline: float = 0.0, marker="circle",
  color=None, line_width=1.5, alpha=1.0, label=None)` — a data element
  (palette slot, legend, events on the heads like Scatter picks).
- **Core.** Per-point segments `(x, baseline) → (x, y)` computed once.
- **Backends.** pg: single `PlotCurveItem` with `connect="pairs"` (one item
  for all stems) + a scatter layer for heads; mpl: `LineCollection` +
  scatter (not `ax.stem` — its container fights the handle contract);
  Plotly: one trace with `None` separators + marker trace.
- Unlocks `stem_plot` ◑→✅, `timeline` ◑→✅ (with Text levels),
  `xcorr_acorr_demo` note. **Effort: S–M.**

### [D116] ErrorBars limit arrows
- **API.** `ErrorBars(..., lo_limit: Accessor | None = None,
  hi_limit: Accessor | None = None)` — optional boolean columns; where
  true, that side's cap is drawn as an arrowhead ("the true value lies
  beyond"), mpl's `lolims`/`uplims` semantic.
- **Core/backends.** Head triangles come from [D107] `_geometry` (same
  ±25° construction, sized from `line_width`); backends draw them as the
  same two-polyline primitive Quiver uses. No new drawing capability
  needed anywhere.
- **Demand note.** Niche; scheduled last in 1.4 and droppable to parked if
  the wave runs long — record the call at review. Unlocks
  `errorbar_limits(_simple)` ❌→✅. **Effort: M.**

### [D120] Docs & example debt (carried follow-ups, now scheduled)
- README + quickstart get the wave 1–3 vocabulary: annotations
  (Arrow/shapes/frame), `bar_labels`, `color_by` on Bars/Curve, explicit
  ticks + templates + minor/rotation, raster norms, Mesh/Quiver, and a
  mosaic screenshot (quickstart has one line today).
- Example 35 (everyday figures) gains panels for the new elements; gallery
  screenshots regenerated with the capture tool.
- api.md spot-check against `FROZEN_1_0` + new exports (the conformance
  suite already enforces registration; this is prose coverage).
  **Effort: S–M, pure docs.**

## 3. Wave 1.5 — fields & flow

### [D117] Contour inline labels (`clabel`)
- **API.** `Contour(..., labels: bool | str = False)` — `True` → the
  level's `%g`; a format-spec string otherwise.
- **Core.** Label placement computed once per level polyline: choose the
  longest path segment's midpoint, angle from the local tangent
  (`atan2(dy, dx)`, normalized to ±90° so text is never upside-down), and
  a mask rectangle so the line visually breaks under the label
  (drawn as a short background-colored segment — cheaper and more portable
  than path clipping). Emits `(x, y, angle, text)` tuples.
- **Backends.** All three draw the existing rotated-`Text` primitive
  ([D96]); *not* mpl's native `clabel`, so the three backends place labels
  identically ([D110] over engine fidelity — record as the decision's core
  trade-off).
- Unlocks `contour_label_demo` ❌→✅, polish on optimization/contour
  recreations. **Effort: M.**

### [D118] `Streamlines` — graduating streamplot from the parked register
- **Why now.** Parked as "M–L after [D107]"; [D107] shipped. With Mesh +
  Quiver + Contour, streamlines are the last member of the standard 2-D
  field quartet; the integrator is self-contained core math.
- **API.** `Streamlines(u, v, *, bounds, density: float = 1.0,
  color=None, line_width=1.5, alpha=1.0, label=None)` — `u`/`v` are 2-D
  arrays on the `Image`/`Contour` grid contract (`bounds` places them in
  data space). Deliberately *not* per-point columns: field topology needs
  the grid.
- **Core.** mpl's algorithm, reimplemented small: seed on a coarse mask
  grid (`30×30 · density`), integrate RK4 both directions with bilinear
  field interpolation, terminate on domain exit / stagnation / occupied
  mask cell (the mask enforces line spacing). Output: list of polylines +
  one mid-line arrowhead each (reusing [D107] head geometry). Pure numpy,
  property-tested (lines stay in bounds; spacing respects the mask;
  uniform field → straight lines).
- **Backends.** Polylines + head polylines — primitives every backend has.
  No per-backend logic beyond the standard renderer trio.
- **Scope cuts (recorded).** No `color_by=speed` gradient lines in v1 (pg
  cannot draw gradient polylines — same honesty tier as `Curve(color_by=)`;
  revisit together), no varying line width, no start-point control.
- Unlocks `plot_streamplot` ❌→✅. **Effort: M–L (the integrator; the
  rendering is trivial).**

## 4. 2.0-gate — [D119] polar decision spike

The last whole projection. **Spike first, decide at review — no
implementation is scheduled by this document.**

- **The problem.** ~11 gallery examples + radar charts. Three collisions:
  (1) R1 — events/`ViewState` are rectilinear `(xlim, ylim)` tuples; polar
  needs `(θ, r)` or a documented cartesian equivalence. (2) pyqtgraph has
  no polar surface at all (hand-built circular grid + transform). (3)
  `AxisSpec` vocabulary (lim/scale/ticks) assumes orthogonal axes.
- **Option A — native polar surfaces** (mpl `projection="polar"`, Plotly
  `polar` subplot, pg hand-built): full fidelity, but three divergent
  implementations, a pg surface built from scratch, and R1 needs a new
  coordinate contract. **XL, architectural.**
- **Option B — polar as a core transform (spike this).** Elements opt in
  via a wrapper (`qv.polar(element, theta=, r=)` or a `PolarSurface`
  option): core transforms `(θ, r) → (x, y)` before the data seam, a
  [D70]-class `PolarGrid` annotation draws the circular grid/spokes with
  existing primitives, and the surface stays rectilinear with
  `aspect=1` — so R1, events, brushes, and backend switching all keep
  working unchanged (they see cartesian). Cost: hover/status readouts show
  x/y not θ/r (could denormalize in the event layer later), no r-axis zoom
  semantics, tick vocabulary limited to what `PolarGrid` draws.
  **M–L, zero architectural risk.**
- **Spike deliverable.** Option B prototype rendering `polar_demo`,
  `polar_bar` (wedges via Polygon), and a radar chart on all three
  backends + a one-page comparison; go/no-go and A-vs-B at the review.
- **Recommendation.** B if the spike's visuals hold up; A only if polar
  becomes a headline use-case (that demand signal does not exist today).

## 5. Explicitly NOT scheduled (re-affirmed parked, with reasons)

| Gap | Status |
|---|---|
| Triangulation (`tri*`, 9 examples) | parked — needs a Delaunay dependency + `TriMesh` contract; no demand signal; grid-precompute + `RawFigure` remain the path |
| Insets / zoom connectors / broken axes | parked — composition-model change (child surfaces + event routing); linked panes cover the analytical job |
| 3+ y-axes | parked — generalizing `y2`→`yN` is mechanical but reads as chart-junk bait; second pane remains the answer |
| axes_grid1 / axisartist toolkits (~32) | permanent non-goals in practice — deep mpl machinery with no portable analog |
| Styling zoos (fancy arrows/boxes, hatching, path effects, locator callbacks) | parked — anti-declarative or pure chrome; escape hatches |
| Eventplot raster | parked — niche; revisit only with [D115] shipped and demand shown |
| Per-point marker shape/rotation | parked — would extend the [D100] channel pipeline; wait for a second concrete ask |
| Curvilinear meshes | parked — [D111] makes the boundary explicit at the API |
| Specialty diagrams (Sankey, skew-T, hillshade, …) | parked — `RawFigure` |

## 6. Decisions summary (to confirm)

- **[D111]** Mesh 1-D-edges validation with a curvilinear-naming error — S
- **[D112]** Quiver `key=` as a truthful legend entry (not axes-fraction) — M
- **[D113]** `Heatmap(cell_labels=)` with core-computed luminance contrast — M
- **[D114]** `norm="symlog"` (`linthresh=`) + `norm="boundary"` (`levels=`)
  through the [D105] core pipeline — M
- **[D115]** `Stem` data element (`connect="pairs"` single-item rendering) — S–M
- **[D116]** ErrorBars `lo_limit`/`hi_limit` arrow caps via [D107] geometry
  — M, droppable
- **[D117]** `Contour(labels=)` — core-placed rotated Text, identical across
  backends — M
- **[D118]** `Streamlines` on the grid contract; RK4 + seeding mask in core;
  graduates from the parked register — M–L
- **[D119]** polar spike (Option B: core transform + `PolarGrid` chrome);
  go/no-go at review — spike M, decision gate
- **[D120]** docs/example debt: README/quickstart/example-35 coverage of
  waves 1–3 — S–M

Plus the unscheduled-but-first **datashader autorange drift** P2 bug at the
top of 1.4.

## 7. Quality gates & verification

Unchanged, per increment: pytest green offscreen (`QT_QPA_PLATFORM=
offscreen`, real exit codes), `mypy src` zero, `ruff` clean, coverage
≥ 88% (currently 92% — new core math is property-tested, which keeps it
up), `mkdocs build --strict`, conformance suite rows for every new
element/option (RENDERERS + HONORED ×3, freeze list, api.md, vocabulary
sets). Each shipped item re-runs its gallery recreation in
`gallery_audit_v2/` and flips the verdict in the re-audit doc — the audit
stays the doc of record for support claims.

## 8. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Diminishing returns — 1.4/1.5 buy ~14 flips vs wave 1's ~45 | that is the point of the strategic read: these items are priced on user value (field quartet completeness, honesty debts, docs) — if an item's value case collapses at spec time, drop it, don't sunk-cost it |
| 2 | Streamline integrator correctness (seeding/termination edge cases) | property tests + golden-image comparison against mpl's output on the gallery field; cut `density` extremes from v1 |
| 3 | Polar spike scope-creeps into implementation | the spike has a fixed deliverable (3 renders + comparison page) and a review gate; no polar code lands on main before the gate |
| 4 | Cell-label/contour-label text volume degrades pg performance | cell-count guard ([D113]); contour labels are ≤ levels-count items — negligible |
| 5 | Vocabulary sprawl ([D54] erosion) | Stem is the only new *element* in 1.4–1.5 besides Streamlines; both pass the ≥2-libraries / ≥2-backends bar; everything else is options on existing elements |
