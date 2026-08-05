# Improvement plan — from 0.3-in-flight to 1.0 (vision refresh)

> A full-project review (2026-07-24, HEAD `ba7b7ed`): code, tests, the design
> corpus, and the weakness/root-cause analyses. Purpose: keep the core vision,
> close the gaps that remain after 0.2, and set the horizon past 0.4 — which the
> current docs stop short of ([`roadmap.md`](roadmap.md) §8 ends at 0.4 +
> "interleaved data layer"; [`future.md`](future.md) predates the rename and is
> stale). Proposed decisions are numbered **[D61]–[D66]**, house style: each is a
> recommendation to confirm at review, not a fait accompli.

## 0. Verified current state

- **Suite green**: 411 passed, 11 skipped (all webengine display-gated), 27 s.
  ~8.6k LOC in `src/qtviz`, 51 test files, CI matrix on 9 OS/Python combos.
- **0.2.0 released** — honor-or-warn ([D51]), capability honesty ([D52]),
  `handle.native` ([D53]) are *implemented*, not just designed. The trust bug
  (silent parameter drops) is fixed and conformance-guarded.
- **0.3 mid-flight** — increment 1 of 4 landed (`AxisSpec` + declarative
  limits/invert/aspect, commit `8d8b936`). Increments 2–4 (log + R1
  normalization, legend contract, legend parity) are open.
- **Housekeeping drift** (small, real):
  - `docs/api.md` doesn't mention `AxisSpec` though it's exported.
  - `roadmap.md` §0 phase-table row `0.2+` still reads ⬜ though 0.2 shipped
    (§8 of the same file says ✅ — internal contradiction).
  - `future.md` is written against the pre-rename project ("No CI, no PyPI, no
    docs site") — the long-horizon doc no longer describes this project.
  - `architecture.md` documents only the legacy webengine bridge.
  - Docs site built but **not deployed** (private repo blocks Pages).

## 1. The vision — what we keep, verbatim

Nothing in this review argues for changing the core position. These invariants
have earned their keep and stay load-bearing:

1. **One immutable, value-hashed `Element`; three interchangeable backends** —
   registered, never imported by core; runtime switching; mixed-backend layouts.
2. **Native Qt, not a web app in disguise** — real QWidgets, GUI-thread
   discipline; webengine is one backend among equals, not the foundation.
3. **100% offline, always** — hard requirement, conformance-tested.
4. **Data-intensive by design** — lazy-first, container-agnostic, out-of-core;
   Datashader as a backend-agnostic pipeline step, not a backend.
5. **Honest capabilities** — honor-or-warn, never silent degradation (0.2's
   lesson, now enforced by conformance tests; this plan extends it, never
   relaxes it).
6. **A small surface you can hold in your head** — curated vocabulary; escape
   hatches (`RawFigure`, `handle.native`) instead of surface sprawl.
7. **No PyPI; release = GitHub tag + Pages docs** ([`RELEASING.md`](../RELEASING.md)).
8. **Standing non-goals reaffirmed** ([D58]): native 3-D, animation API,
   cross-backend Overlay, single vector export across mixed backends,
   live-item-on-Element. Plus `future.md`'s push-backs (REST remote control,
   no-code builder, layout DSL).

**The one-sentence vision, sharpened for the horizon:** *qtviz should become the
obvious way to put live, large, linked data on a desktop — the plotting layer
where 50M rows, a streaming feed, and a brush-linked dashboard are all native
Qt widgets described as immutable data.* §4 stages toward exactly that.

## 2. Gap register — what remains after 0.2

Grouped by disposition. (Full provenance: `developer-perspective-weaknesses.md`,
`weakness-root-causes.md`, `capabilities-gaps.md`, `matplotlib-capability-review.md`.)

### 2a. In flight — finish before anything else
| Gap | Where it's specced |
|---|---|
| Log/symlog scales + **R1 coordinate normalization** (the load-bearing risk) | `milestone-0.3-firstclass.md` incr. 2 |
| Legend contract (`legend_entry()`, `label`, Overlay aggregation) | incr. 3 |
| Legend parity (webengine `showlegend`, pyqtgraph gradient colorbar) | incr. 4 |

### 2b. Planned, milestoned (0.4 + interleaved) — keep
BoxPlot/Violin, grouped/stacked `Bars`, real `Heatmap.aggregator` ([D54]);
composite raster export + cross-pane chrome ([D57]); `DataSource`
(Parquet/DuckDB/SQL) + pushdown + versioned result cache (Phase 5); raster
selection pixel→rows ([D58], sequenced after sources).

### 2c. Deferred with a reason — the reason now has an expiry date
| Gap | Deferred because | Disposition |
|---|---|---|
| **datetime/`time` axes + tick formats** | data layer lacks datetime dtype | **Deprioritized by owner ruling (2026-07-24, [D62] resolved)** — parked, revisit on demand; the time-series examples keep numeric axes |
| Datashader `logx`/`logy` | axis seam only just landing | unlocks naturally once 0.3 incr. 2 lands |
| Incremental/partial update ([D7] coalescing; rebuild is the only path) | reactive shipped View-root first | blocks any credible streaming story → **0.6, [D63]** |
| Gridded regrid, `spread`/`dynspread`, multi-agg `summary`, datashader line styling | coverage tail | batch behind demand; fold regrid into 0.5 (it's a data-scale item) |
| webengine W5.2 binary transport | gated on measured need | keep gated — the gate is correct |
| HoloViews L2 bidirectional streams, `.qtviz` accessor | one-way covers most value | keep parked pending user pull |

### 2d. Never milestoned — the plan's new content
| Gap | Assessment |
|---|---|
| **Annotation & reference layer** (h/v lines, spans, text, threshold bands) | mpl-review gap #4; the telemetry example hand-rolls tolerance bands today. Fits the element model *cleanly* (pure-data elements, trivially portable across backends — general and composable, not a bolt-on). → **0.4, [D61]** |
| **Color normalization** (log/diverging/discrete norms for `color_by`/rasters) | small, extends `core/encoding.py`; pairs with log axes conceptually → **0.4, [D61]** |
| Twin/secondary axes | real demand in the target audience; touches the axis seam → decide at 0.5 scoping, after 0.3's axis model settles |
| Contour/quiver/streamplot | demand-gated; candidates for a later vocabulary round, not 0.4 |
| Export knobs (dpi, transparent, metadata) | small, niche; batch into 0.4's export work |
| Ecosystem/maturity (weakness 1.8: nobody can try it) | **accepted by design** — owner ruling (2026-07-24, [D64] resolved): the repo stays private permanently; docs stay local (`mkdocs serve`/`mkdocs build`) |

### 2e. Process/infra gaps
- No type checking in CI; no coverage gate (future.md hardening list, still valid).
- No guard against docs drift (the `AxisSpec` miss shows the failure mode).
- The long-horizon doc (`future.md`) is dead; `architecture.md` mislabeled.

## 3. Immediate housekeeping (fold into the 0.3 release, ~an afternoon)

1. `docs/api.md`: document `AxisSpec` (+ whatever 0.3 adds) — and add a tier-1
   test asserting every name in `qtviz.__all__` appears in `docs/api.md`, so
   docs drift fails the suite instead of accumulating.
2. `roadmap.md` §0 phase table: mark 0.2 ✅ released (match §8).
3. Replace `future.md` with this plan's §4 horizon (archive the old one — its
   still-live ideas are absorbed below); re-title `architecture.md` as
   *"legacy webengine bridge architecture"* with a pointer to `spec.md`.
4. Add `mypy` (or pyright) over `src/qtviz` public modules to CI as
   non-blocking first, blocking at 1.0 ([D66]).

## 4. The staged plan — 0.3 → 1.0

Cadence unchanged: spec → plan → discussion-items → benchmarks → TDD, review at
each increment boundary; each release coherent and honest. Direction is
confirmed at each release boundary — this table is a proposal, not a schedule.

### 0.3 — First-class axes + legends *(finish as specced)*
Increments 2–4 of `milestone-0.3-firstclass.md`, unchanged. Plus §3
housekeeping in the release PR. **Exit:** the milestone's acceptance scenario
(log axis + two-entry legend + data-space brush on all three backends).

### 0.4 — Vocabulary, annotation & export *(planned scope + [D61])*
- As planned: `BoxPlot`/`Violin`, grouped/stacked `Bars`, real
  `Heatmap.aggregator` ([D54]); composite raster export + chrome coordinator
  ([D57]); export knobs folded in.
- **[D61] adds:** the annotation/reference layer as curated elements
  (`HLine`/`VLine`/`Span`/`Text` — pure data, composable via `*`), and color
  normalization (`norm="log"|"symlog"|diverging|discrete` on the encoding path,
  honored-or-warned per backend).
- **Exit:** the telemetry example rebuilt with real reference elements instead
  of hand-rolled bands; a statistical dashboard (box + grouped bars) renders on
  all three backends; a mixed layout exports one PNG.

### 0.5 — Sources *(the interleaved Phase-5 work; [D62] resolved: no datetime)*
Theme: *real data lives in files and databases.*
- `DataSource` protocol: Parquet + DuckDB first, SQL after; background queries;
  versioned result cache (as long specced in Phase 5).
- Datashader follow-ons that are really data-scale items: `logx`/`logy`
  routing, gridded regrid. Twin-axes decision taken here; tick-format
  vocabulary (feasibility Phase D) is a candidate if there's room.
- datetime axes are **parked** per the owner ruling — revisit only on demand.
- **Exit:** a 50M-row Parquet → datashaded dashboard without materializing the
  table, viewport pushdown reaching the source.

### 0.6 — Live & linked *(the differentiator release, [D63])*
Theme: *the reason to choose native Qt over a notebook.* No other Python
plotting stack does low-latency streaming + linked brushing at 50M rows as
plain desktop widgets — this release makes that the headline.
- Incremental update path: `RenderHandle.update` diffing where cheap, [D7]
  update coalescing, append-optimized Curve/Scatter on pyqtgraph (its declared
  `streaming` capability finally backed by a real code path — [D52] honesty
  applied to ourselves).
- Streaming sources behind the existing reactive seam (`Signal`-driven append;
  rolling windows lifting the spec's "stream-time auto-rolling" deferral).
- Raster selection (pixel → source rows), unlocked by 0.5's source layer →
  linked brushing/crossfilter *through* a datashaded view.
- **Exit:** a live telemetry dashboard — streaming feed, rolling window,
  datashaded history, brush on the raster filters a linked panel — at
  interactive frame rates, ≤100 LOC.

### 1.0 — Stability *(the promise release, [D66])*
- API freeze + documented deprecation policy; remove the `qtwebplot` shim and
  `Options` (both already two-release-tracked).
- Docs completeness: "writing a backend" tutorial (the extensibility story
  deserves first-class docs), gallery refresh, benchmark page.
- CI: type check blocking; coverage gate (~80%, excluding examples).

### Parked (unchanged stance, revisit on demand)
W5.2 binary transport (measured need) · HoloViews L2 + `.qtviz` accessor ·
public element registry ([D54] — third-party demand) · contour/quiver ·
**Studio** (post-1.0; 0.6's streaming + 0.5's sources are exactly its
substrate, so nothing here is thrown away if Studio goes ahead) · 3-D /
animation (non-goals; `RawFigure` remains the answer).

## 5. Proposed decisions (confirm at review)

- **[D61] 0.4 grows an annotation/reference layer + color norms.**
  *Alternatives:* keep 0.4 minimal as specced (defers the gallery's most
  hand-rolled pattern again); a freeform draw-API (rejected — violates
  purity/portability; elements keep it declarative).
- **[D62] — RESOLVED (owner, 2026-07-24): datetime axes are not a priority.**
  0.5 is data sources alone; datetime/`time` scale parked, revisit on demand.
- **[D63] 0.6 = streaming/incremental + raster selection as the flagship.**
  *Alternatives:* jump to Studio (rejected: library differentiators first —
  Studio inherits them); vocabulary round 2 (weaker story, no new capability).
- **[D64] — RESOLVED (owner, 2026-07-24): the repo stays private, permanently.**
  Weakness 1.8 is accepted by design; docs remain local; no Pages, no publish.
- **[D65] Docs-drift guard**: `__all__` ⊆ `docs/api.md` as a tier-1 test (§3).
- **[D66] 1.0 bar**: freeze + shim removal + blocking typecheck + coverage
  gate, as listed above.

## 6. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | 0.3 R1 normalization slips and delays everything queued behind the axis seam | it's already the milestone's top risk with TDD strategy specced; nothing in this plan lands before 0.3 closes |
| 2 | [D61] scope-creeps 0.4 (annotations invite endless variants) | curated cut: 4 element types, one review boundary; the vocabulary stays curated per [D54] |
| 3 | datetime dtype ripples wider than the axis path (accessors, expressions, datashader, transport) | parked with the feature ([D62]); if ever revived, start with a dtype-propagation feasibility pass, same pattern as `axis-surface-feasibility.md` |
| 4 | streaming (0.6) tempts mutation into Elements | the seam is fixed in advance: signals + handle-level update only; Elements stay immutable — [D38]'s View-root precedent |
| 5 | horizon plan re-becomes an autonomous feature march | direction confirmed at every release boundary; §5 decisions are explicitly to-confirm, not decided |
