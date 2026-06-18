# qtviz — roadmap (library + Studio)

> Companions: `native-pivot-research.md` (why we picked Option B + adapter
> over extending HoloViews); `dask-datashader-research.md` (why we
> integrate with Datashader/Dask rather than compete).
>
> Working name: `qtviz` (renamed from `qtwebplot` — see pivot doc §7).

## 0. Current status & revised sequence

Built and green: **Phase 1** (core + pyqtgraph), **Phase 2** (matplotlib), the
**data layer** (functional accessors + out-of-core dask/xarray/zarr adapters —
originally Phase 5 work, pulled forward), and **Datashader** (big-data raster +
viewport re-aggregation — Phase 4's rendering half).

The build order **diverged from the phase numbering**. With the two native
backends proven, we hardened the data layer and shipped Datashader *before* the
HoloViews adapter (Phase 3) and reactive signals (Phase 4's other half) — because
the data-intensive path is the library's reason to exist, and a strong, lazy-first
data core had to come first. Net effect:

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | rename · CI · spikes | ✅ rename done; spikes folded into Phase 1; **CI matrix ✅** (macOS/Lin/Win × 3.11–3.13) |
| 1 | core compose + pyqtgraph | ✅ |
| 2 | matplotlib backend | ✅ |
| 3 | HoloViews adapter | ✅ Spike-P2 [D41]; **3a static `from_holoviews` ✅** (8 elements + Points/Area, containers, RawFigure fallback); **3b ✅** — `DynamicMap`→`Signal[Node]` one-way ([D44] L1) + `from_hvplot` ([D43] Path A); L2 bidirectional streams + `.qtviz` accessor deferred — see `milestone-holoviews-adapter.md` §7 |
| 4 | reactive + Datashader | **Datashader ✅**; **reactive `Signal` ✅** (View-root, S-style; crossfilter) |
| 5 | data layer + webengine | **lazy adapters ✅** (dask/xarray/zarr); Parquet/DuckDB/SQL sources ⬜; webengine rehome ◑ (**W0–W4 ✅ · W5.1a base64 transport ✅ · W5-offline (no-CDN) ✅**; W5.2 binary-fetch tail ⬜ deferred — see `webengine-arrow-transport.md` §10) |
| 6 | release `0.1` | ✅ **released** — `v0.1.0` tag + GitHub prerelease (0.1.0 metadata · docs/CHANGELOG · mkdocs site · API docstrings); **Pages deploy deferred** (private repo / plan blocks Pages — see `RELEASING.md`). PyPI publish **not a goal** |
| 0.2+ | post-0.1 (R1–R6) | ⬜ staged **0.2** hardening+escape-valve · **0.3** first-class axes+legends · **0.4** vocabulary+composite — see §8 + `weakness-root-causes.md` |

**Recommended next order** (detail in §8 + `weakness-root-causes.md`): 0.1 is **released**
(tag + GitHub prerelease; Pages deploy deferred). Next is the **staged post-0.1 plan**
driven by root causes R1–R6 — **0.2** hardening + escape valve (enforce §3.4 honor-or-warn,
capability honesty, `handle.native`), **0.3** first-class axes (the axis-surface Phase B,
already spiked) + legends, **0.4** grow built-in elements + composite export — with the
**Phase-5 data layer** (Parquet/DuckDB, then raster selection) interleaving. The phase
tables below are retained as the original estimate/acceptance reference.

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  qtviz Studio   (Phases 7+)                                         │
│  Qt desktop app — sources · canvas · inspector · pipeline · projects│
├─────────────────────────────────────────────────────────────────────┤
│  qtviz.reactive   (Phase 4)                                         │
│  Signal · derived · effect · dispose (QObject-tied)                 │
├─────────────────────────────────────────────────────────────────────┤
│  qtviz.compose   (Phase 1)                                          │
│  Element · Overlay (*) · Layout (+) · Splitter · Tabs · Dock        │
├─────────────────────────────────────────────────────────────────────┤
│  qtviz.adapter   (Phase 3)                                          │
│  from_holoviews · wrap_mpl_hv · .hvplot extension                   │
├─────────────────────────────────────────────────────────────────────┤
│  Backend: pyqtgraph │ Backend: matplotlib │ Backend: webengine      │
│  (Phase 1, primary) │ (Phase 2)            │ (Phase 5 — existing)   │
│  OpenGL / native    │ FigureCanvasQTAgg    │ existing WebBridgeView │
├─────────────────────────────────────────────────────────────────────┤
│  qtviz.data    (Phase 5)        qtviz.transport  (Phase 5)          │
│  DataSource · Parquet · Dask    Arrow IPC for webengine backend     │
├─────────────────────────────────────────────────────────────────────┤
│  qtviz.theme   (today, carryover)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

**Element render flow**:

```
user: Scatter(table, x="a", y="b") * Curve(table, x="a", y="b_smooth")
                                       │
                                       ▼   compose
                            Overlay([Scatter, Curve])
                                       │
                                       ▼   .render(backend="pyqtgraph")
                            PyQtGraphRenderer
                                       │
                                       ▼
                            GraphicsLayoutWidget
                                + ScatterPlotItem
                                + PlotCurveItem
                                       │
                                       ▼
                            QWidget — drop into any Qt app
```

For >10M points: same path, but `Scatter` auto-routes through
Datashader → `pg.ImageItem` overlay with viewport-driven
re-aggregation.

## 2. Module layout (target)

```
src/qtviz/
├── core/                       # Phase 1
│   ├── element.py              # Element base class, ElementSpec
│   ├── overlay.py              # Overlay (*)
│   ├── layout.py               # Layout (+), Splitter, Tabs, Dock
│   ├── event.py                # typed events: Range, Pick, Select, Hover, Tap
│   ├── theme.py                # carryover from current
│   └── backend.py              # Backend Protocol
├── elements/                   # Phase 1
│   ├── scatter.py              # Scatter(table, x, y, color, size)
│   ├── curve.py                # Curve(table, x, y)
│   ├── bars.py                 # Bars
│   ├── image.py                # Image(array, bounds)
│   ├── heatmap.py              # Heatmap(table, x, y, z)
│   ├── histogram.py            # Histogram
│   ├── errorbars.py            # ErrorBars
│   └── spread.py               # Spread (band fill)
├── backends/
│   ├── pyqtgraph/              # Phase 1
│   │   ├── renderer.py
│   │   ├── scatter.py          # one file per element
│   │   ├── curve.py
│   │   ├── ...
│   │   └── _events.py          # sigRangeChanged → Range event
│   ├── matplotlib/             # Phase 2
│   │   ├── renderer.py
│   │   ├── canvas.py           # FigureCanvasQTAgg wrapper
│   │   ├── scatter.py
│   │   ├── ...
│   │   └── _events.py
│   └── webengine/              # Phase 5 — existing qtwebplot code rehomed
│       ├── view.py             # WebBridgeView (current)
│       ├── plotly.py           # current PlotlyBackend
│       ├── bokeh.py            # current BokehBackend
│       └── holoviews.py        # current HoloViewsBackend
├── adapter/                    # Phase 3
│   ├── holoviews.py            # from_holoviews(hv_obj)
│   ├── mpl_holoviews.py        # wrap_mpl_hv(hv_obj)
│   └── hvplot_ext.py           # hvplot extension hook
├── reactive/                   # Phase 4
│   ├── signal.py               # Signal / derived / effect
│   └── scope.py                # dispose, QObject lifecycle
├── data/                       # Phase 5
│   ├── source.py               # DataSource Protocol
│   ├── arrow.py / parquet.py / csv.py / dask.py / sql.py
│   └── stream.py
└── ext/
    └── datashader/             # Phase 4
        └── shader.py           # rasterize → pg.ImageItem
```

```
qtvizstudio/                    # Phases 7+ (separate package)
├── app.py / main_window.py
├── project/                    # project file format
├── sources/ canvas/ inspector/ pipeline/
└── plugins/
```

## 3. Phases

Each phase: deliverables · acceptance · risks. Length = full-time
estimate.

### Phase 0 — Pivot prep + spikes (1 month) · ✅ rename + CI matrix done; spikes folded into Phase 1

| Deliverable                                                | Acceptance                                          |
|------------------------------------------------------------|------------------------------------------------------|
| Rename `qtwebplot` → `qtviz`; old code moves under `backends/webengine` | Tests pass on new paths; old import path errors with hint |
| GitHub Actions CI matrix (macOS/Lin/Win × 3.11/3.12/3.13)  | All current tests pass on all platforms              |
| GitHub repo/names reserved (`qtviz`, `qtvizstudio`)         | Reservations confirmed (PyPI publish out of scope)   |
| Doc site (mkdocs-material) skeleton                         | Quickstart hosted                                    |
| **Spike P1** — pyqtgraph `GraphicsLayoutWidget` with linked X axes + brush event → Qt signal | One example: scatter + curve, brush selects points, signal fires |
| **Spike P2** — render `hv.Scatter` via prototype adapter to pyqtgraph | `qtviz.from_holoviews(hv.Scatter(df, "a", "b"))` returns a QWidget that draws |
| **Spike P3** — `holoviews.render(obj, "matplotlib")` wrapped in `FigureCanvasQTAgg` with theme propagation | One example renders a HoloViews `Overlay` via mpl in a Qt window |
| **Spike D1** — 1M-row `pg.ScatterPlotItem` interactive | 30+ FPS pan/zoom + brush response < 16ms              |

**Acceptance.** All four spikes return concrete numbers / working
demos. If P2 is impractical (HoloViews tree walking too brittle), Option
A is also dead — we drop the adapter and ship Option B alone.

**Risks.** Spike P2 is the gate. If `from_holoviews` requires reading
HoloViews internals that change every release, the adapter becomes a
maintenance sink and we cut it.

### Phase 1 — Core compose + pyqtgraph backend (2.5 months) · ✅ done

| Deliverable                                          | Acceptance                                           |
|------------------------------------------------------|-------------------------------------------------------|
| `qtviz.Element` base + 8 element types               | Scatter · Curve · Bars · Image · Heatmap · Histogram · ErrorBars · Spread |
| `Overlay` (`*`) and `Layout` (`+`) composition       | `Scatter() * Curve()` overlays in one ViewBox; `Scatter() + Curve()` puts them side-by-side |
| `Splitter` / `Tabs` / `Dock` Qt-native composition   | Reuse current `layouts.py` patterns                  |
| Typed event protocol: `Range`, `Pick`, `Select`, `Hover`, `Tap` | Each event has a `(source, payload)` tuple |
| pyqtgraph backend for all 8 elements                 | Renders correctly in `GraphicsLayoutWidget`          |
| Theme propagation through pyqtgraph                  | One `Theme` styles axes/bg/palette                   |
| Linked axes via composition                          | `Scatter() + Curve()` with `link_x=True` shares X    |
| 5 example scripts                                    | Each one < 40 LOC, runnable                          |

**Acceptance milestone.** A 3-panel dashboard (Scatter + Histogram +
Curve) with shared X axis, linked brushing, and a `Theme.dark()` —
under 60 LOC, 100% pyqtgraph, no JS, no webengine.

**Risks.**

- Composition semantics (overlay vs layout vs link) take design iteration.
  Mitigation: lift from HoloViews' model; we're not inventing.
- pyqtgraph event API has rough edges (e.g., picking on `ScatterPlotItem`
  requires custom clickable). Mitigation: small wrapper classes per
  element.

### Phase 2 — Matplotlib backend (1.5 months) · ✅ done

| Deliverable                                          | Acceptance                                           |
|------------------------------------------------------|-------------------------------------------------------|
| `FigureCanvasQTAgg` wrapper with toolbar             | Drop-in widget                                       |
| mpl backend for all 8 elements                       | Same Element renders correctly through mpl            |
| Event bridge: mpl events → typed `Range`/`Pick`/`Select` | Brush rectangle from mpl emits qtviz Select event |
| Theme propagation through mpl                        | Same `Theme` styles mpl as it does pyqtgraph         |
| `wrap_mpl_hv(hv_obj)` helper                         | `holoviews.render(obj, "matplotlib")` → Qt widget    |
| Performance baseline                                 | 100k point scatter mpl vs pyqtgraph table in README  |

**Acceptance milestone.** Same dashboard from Phase 1, swap backend
attribute → renders entirely in matplotlib via `FigureCanvasQTAgg` with
toolbars. Both backends pass the same test suite.

**Risks.** mpl picking has known fiddliness; spec the typed events
clearly and accept that mpl may need polling for some events.

### Phase 3 — HoloViews adapter (1 month) · ✅ done — 3a static + 3b DynamicMap/hvplot (L2 streams + `.qtviz` accessor deferred)

| Deliverable                                          | Acceptance                                           |
|------------------------------------------------------|-------------------------------------------------------|
| `qtviz.from_holoviews(hv_obj)` for our 8 elements    | Each translates correctly                            |
| Overlay / Layout / GridSpace translation              | HoloViews `(scatter * curve) + image` works         |
| `DynamicMap` support                                  | Updating the DynamicMap re-renders the QWidget       |
| HoloViews `Stream` → qtviz event translation          | `RangeXY` stream fires when ViewBox range changes    |
| `hvplot` extension registration                       | `df.hvplot(kind="scatter", backend="qtviz")` works   |
| Unsupported elements raise clearly                    | `qtviz.from_holoviews(hv.Sankey(...))` → "unsupported in qtviz adapter; use webengine backend or hv.render" |

**Acceptance milestone.** A pandas user imports `qtviz.hvplot_ext`,
calls `df.hvplot(kind="scatter")`, gets a native-Qt widget rendering
through pyqtgraph. No browser, no Bokeh server.

**Risks.** HoloViews internal API drift. Mitigation: pin a tested
range; CI tests against the pinned and latest HoloViews to catch
breakage early.

### Phase 4 — Reactive + Datashader (1.5 months) · ✅ Datashader + reactive done (coverage follow-ups in `capabilities-gaps.md` §1)

> **Status.** Both halves of this phase shipped. Datashader landed *as a backend-agnostic
> pipeline transform* (Scatter→Image in `resolve_node`), not the pyqtgraph-only
> `pg.ImageItem` path this table assumed — it works on every backend, out-of-core, with
> debounced viewport re-aggregation and hover reverse-lookup [D18–D22, D46,
> `milestone-phase4-datashader.md`]. The reactive `Signal` layer (View-root binding +
> crossfilter) is in too [D38–D40]. Coverage follow-ups in `capabilities-gaps.md` §1.

| Deliverable                                          | Acceptance                                           | Status |
|------------------------------------------------------|-------------------------------------------------------|--------|
| `qtviz.reactive` — Signal / derived / effect / batch  | S-style auto-tracking; GUI-thread; dispose semantics | ✅ |
| **View-root** reactive binding (`View(Signal[Node])`) | Changing the signal re-renders the View (debounced); Elements stay pure — D38 chose View-root over `Element(data=signal)` | ✅ |
| Linked brushing across views via signals              | Brush on one Scatter filters another (example 21)    | ✅ |
| `ext.datashader` integration                          | `Scatter(table, scale="datashader")` aggregates out-of-core; backend-agnostic raster | ✅ |
| Viewport-driven re-aggregation                        | Pan/zoom triggers debounced re-aggregation          | ✅ |
| Crossfilter rewrite                                    | shipped as `examples/21_reactive_crossfilter.py` — signals + native Scatter, offline | ✅ |

**Acceptance milestone.** Reactive crossfilter dashboard, 10M rows,
pyqtgraph backend, Datashader for any single view that exceeds 1M
visible points. ≤80 LOC.

**Risks.** Datashader → pg.ImageItem rasterization round-trip latency.
Mitigation: spike during Phase 0; if >100 ms typical, drop to
mpl-rendered Datashader image.

### Phase 5 — Data layer + webengine backend rehome (2 months) · ◑ lazy adapters + webengine rehome done; Parquet/DuckDB sources + W5.2 binary transport open

> **Status.** The lazy-first *adapter* layer this phase implied is already built —
> container-agnostic `DataRef` adapters for dask/xarray/zarr (wrap existing
> in-memory lazy objects), out-of-core and off-thread [D1, D17, `milestone-data-core.md`].
> What remains here is the *source* layer below (`DataSource` reading Parquet/DuckDB/
> SQL/CSV from disk or a DB) — still ⬜. The **webengine backend rehome is done**
> (`webengine-rehome.md`): the legacy Qt↔JS bridge now sits behind the native Backend
> protocol, with qtviz's layouts/linking superseding the legacy ones, and the adapter
> falls back to it for elements qtviz doesn't natively model. W0–W4 + base64 transport +
> offline (no-CDN) shipped; only the W5.2 binary `fetch` transport tail is deferred.

| Deliverable                                          | Acceptance                                           |
|------------------------------------------------------|-------------------------------------------------------|
| `qtviz.data.DataSource` Protocol                     | 5 source types implement it                          |
| `Parquet` / `CSV` / `Arrow` / `Dask` / `SQL` sources | Each lazy where possible                             |
| `DuckDB`-backed query layer                          | `Query("SELECT … FROM src WHERE …")` → Arrow         |
| Background-thread queries                             | No GIL stall in UI                                   |
| Query result cache                                    | Versioned LRU                                        |
| Webengine backend rehomed under `qtviz.backends.webengine` | Existing Plotly/Bokeh/HoloViews(JS) backends work unchanged via new namespace |
| Webengine `Element` adapters                          | `Scatter` renders through Plotly backend if `backend="webengine"` |
| Arrow IPC binary transport for webengine backend     | <100ms for 100 MB Arrow payload                      |

**Acceptance milestone.** 50M-row Parquet → `qtviz.Scatter(query, x, y)`
renders via pyqtgraph + Datashader by default; switching `backend="webengine"`
renders via Plotly. Same Element, three backends, user picks.

**Risks.** Element-API matchup with three backends has long tail of
edge cases. Mitigation: define minimum viable Element API; backends
declare unsupported options rather than silently ignoring.

### Phase 6 — Library 0.1 release (1 month) · ◑ in progress — release prep done; Pages deploy remains (PyPI publish is **not a goal**)

| Deliverable                                          | Acceptance                                           |
|------------------------------------------------------|-------------------------------------------------------|
| Doc site complete                                     | Tutorial, gallery (10 examples), API reference       |
| Tagged `qtviz 0.1.0` release on GitHub                | `pip install git+…` / from source works (no PyPI)    |
| Migration guide (`qtwebplot` → `qtviz`)               | Old import shim with deprecation warning             |
| Benchmark page                                        | pyqtgraph vs mpl vs webengine perf for representative payloads |
| Demo videos                                           | 3 short videos                                        |

**Acceptance milestone.** New user installs qtviz, runs the quickstart,
builds the 3-panel example. No friction.

**Risks.** Bug tail. Mitigation: 2 weeks of testing buffer included.

### Phase 7–9 — Studio (deferred, optional, 5+ months)

Same structure as the prior plan's Phases 5–8 (Studio shell, pipeline,
connectors, polish), but now the *Studio plots through qtviz Elements*
rather than directly through `WebBridgeView`. This means:

- Studio canvas hosts qtviz Elements with selectable backends.
- pyqtgraph backend gives Studio the real-time / interactive feel
  HoloViz / Tableau / Streamlit can't.
- Studio gets matplotlib export for free (any plot → `Theme` → mpl →
  PDF/PNG/SVG).
- Studio still uses the webengine backend for any Plotly/Bokeh-specific
  scenarios.

Studio scope is deferred until after Library 0.1 — it's not the first
ship gate anymore.

## 4. Total scope

| Phase | Length     | Cumulative |
|-------|------------|------------|
| 0     | 1 month    | 1          |
| 1     | 2.5 months | 3.5        |
| 2     | 1.5 months | 5          |
| 3     | 1 month    | 6          |
| 4     | 1.5 months | 7.5        |
| 5     | 2 months   | 9.5        |
| 6     | 1 month    | 10.5       |

**Library 0.1 ships at ~10.5 months full-time** — the real first
milestone. Studio adds another 5+ months on top.

Compared to the previous roadmap (15.5 months to Studio 0.1, 8.5 to
library 0.1): library timeline is ~2 months longer because we're
shipping three backends, not one. Studio timeline is shorter overall
because Studio gets to leverage the qtviz Element layer rather than
inventing on top of `WebBridgeView`.

## 5. Critical path

```
0 ✅ ─→ 1 ✅ (pyqtgraph) ─→ 2 ✅ (mpl) ─→ 3 ✅ (hv adapter) ─→ 4 ✅ (reactive+datashader)
   ─→ 5 ◑ (data layer ✅ + webengine ✅; Parquet/DuckDB sources open) ─→ 6 ◑ (lib 0.1: prep done, docs deploy remains)
```

The Phase-0 spike gates have all been cleared: P1 (pyqtgraph composition) and P2
(HoloViews adapter feasibility, [D41]) both passed, so the adapter shipped rather than
being cut. The remaining critical path is Phase 5's data sources, then the 0.1 release.

## 6. Risks (ranked)

| #  | Risk                                                                    | Mitigation                                                        |
|----|-------------------------------------------------------------------------|-------------------------------------------------------------------|
| 1  | Three backends triples the surface area for tests/bugs                  | Define minimum viable Element API; backends declare unsupported options |
| 2  | pyqtgraph at 10M+ points without OpenGL is slow                         | Use `useOpenGL=True`; fallback to Datashader at >1M                |
| 3  | HoloViews adapter rots with HoloViews releases                          | Pin tested range; CI on pinned + latest                            |
| 4  | mpl event integration too clunky for interactive flows                  | Spec mpl as the "static + slow-interactive" backend; pyqtgraph for live |
| 5  | Composition semantics (Overlay/Layout/link/share-axis) take design iteration | Lift from HoloViews; don't reinvent                          |
| 6  | Renaming `qtwebplot` → `qtviz` breaks downstream users                  | Provide import shim for 2 releases with deprecation warning        |
| 7  | Datashader → pg.ImageItem round-trip slower than expected               | Spike in Phase 0; fallback to mpl-rendered datashader image        |
| 8  | Studio scope creep delays library ship                                  | Library 0.1 is the gate; Studio is post-1.0                        |

## 7. Decisions needed before Phase 0

| # | Decision                            | Recommendation                                                  |
|---|-------------------------------------|------------------------------------------------------------------|
| 1 | Project rename target               | **`qtviz`** — see pivot doc §7                                  |
| 2 | Backends in scope for 0.1           | **pyqtgraph (primary), matplotlib, webengine (rehome)**         |
| 3 | HoloViews adapter scope             | **One-way: `from_holoviews()` for our 8 elements**              |
| 4 | Element vocabulary cut for Phase 1  | **Scatter, Curve, Bars, Image, Heatmap, Histogram, ErrorBars, Spread** |
| 5 | Datashader integration              | ~~Native via `pg.ImageItem`~~ → **as-built: backend-agnostic pipeline transform (Scatter→Image), works on every backend; `scale="auto"` routes at a configurable threshold [D18–D21]** |
| 6 | deck.gl / WebGL                     | **Only via webengine backend, not a Phase ≤6 deliverable**      |
| 7 | Auto-backend policy                  | **User-chosen with sane defaults; no magic routing**            |
| 8 | License                              | **MIT**                                                          |
| 9 | Studio: same repo or separate?       | **Same repo until Phase 7; split at Studio 0.1**                |
| 10| Old `qtwebplot` users                | **Import shim + deprecation warning for 2 releases**            |
| 11| Telemetry                            | **None in library; opt-in in Studio later**                     |

## 8. What to do next

> The original Phase-0 startup steps (confirm decisions §7, run the spikes, rename, set up
> CI) are all complete. This section now tracks the remaining work toward and beyond 0.1.

### Post-0.1 plan — staged 0.2 → 0.3 → 0.4 (root causes R1–R6)

`developer-perspective-weaknesses.md` + `weakness-root-causes.md` decomposed the
abstraction tax into six root causes (R1 purity invariant · R2 LCD vocabulary · R3
extensibility asymmetry · R4 unenforced contracts · R5 axes/legends modeled late · R6
no unified scene). The response is **staged**, each release coherent and reviewable
(decisions [D51]–[D58]):

- **0.2 — Hardening + escape valve (R4, R1).** ✅ **released (`v0.2.0`).** Made the
  existing surface *honest* + a native escape hatch — no new chart features.
  `milestone-0.2-hardening.md` ([D51]–[D53]).
  - **DP1** — enforce §3.4 as **honor-or-warn** ([D51]): wire the trivial silent drops
    (`marker`, pyqtgraph `alpha`/`line_style`, `interpolation`), warn-and-degrade the
    unbuilt (`aggregator`, `group`), guard with a conformance test; **capability
    honesty** ([D52], `dimensions={2}`/`animation=False`); **deprecate** dead `Options`.
  - **DP3** — `handle.native(element_id)` ([D53]): the purity-preserving accessor to the
    live backend object (ROIs, crosshairs, native signals) — relieves the interaction
    *and* escape-hatch ceilings without widening the portable contract.
- **0.3 — First-class concepts (R5).** ◑ **in progress** — spec:
  `milestone-0.3-firstclass.md` ([D59]/[D60]). Promote the two afterthoughts to real models.
  - **DP4** — axes: `AxisSpec` + a coordinate-transform stage ([D56]) — log / symlog /
    datetime / limits / invert / tick-format. **This is the existing axis-surface item
    below (Phase B, already spiked)**; also unlocks datashader `logx`/`logy`.
  - **DP5** — legends: a per-element `legend_entry()` contract + overlay aggregation +
    webengine legends + a true gradient colorbar ([D55]).
- **0.4 — Vocabulary + edges (R3 partial, R6).**
  - **[D54]** — grow built-in elements where demand is clear (`BoxPlot`/`Violin`,
    grouped/stacked `Bars`, a real `Heatmap.aggregator`). The element vocabulary stays
    **curated**; a public element registry + `qtviz.elements` entry-point is parked.
  - **DP6** — composite raster export + cross-pane chrome coordinator ([D57]).
- **Interleaved — data layer (existing Phase 5).** `DataSource` (Parquet/DuckDB/SQL)
  proceeds alongside; it also unblocks **raster selection** (pixel→source-rows, [D58])
  which is sequenced *after* the source/pushdown layer, not as a rendering feature.
- **Non-goals ([D58]).** live-item-on-Element (use `native()`), cross-backend Overlay,
  single vector export across backends, 3-D, animation — documented edges, revisitable.

The remaining items below are retained for detail and slot into the stages as noted.

1. **0.1 release** — ✅ tagged `v0.1.0` + GitHub prerelease created (source/`pip install
   git+…`-installable; PyPI publish is **not a goal**). **Docs-site Pages deploy
   deferred** — the repo is private and the plan blocks Pages; revisit by making the
   repo public or upgrading the plan, then `gh workflow run docs.yml` (see `RELEASING.md`).
2. **Data sources (Phase 5)** — `DataSource` for Parquet/DuckDB/SQL behind the lazy
   `DataRef` contract; background queries; versioned result cache.
3. **Axis transforms (the axis-surface seam)** — **(→ 0.3 / DP4 / [D56])** — title/labels,
   log / symlog / datetime, limits, and tick formatting across all backends, built on one
   shared per-surface config step (`surface_of` + `apply_surface`). Design + cross-backend
   feasibility in
   [`axis-surface-feasibility.md`](axis-surface-feasibility.md). Phased:
   - **Phase A ✅ (shipped)** — `surface_of` + `apply_surface` wire the previously-dead
     `OverlayOptions` title / `x_label` / `y_label` on pyqtgraph, matplotlib, and
     webengine; `tests/qtviz/test_surface.py`. (Value review: feasibility report §9 —
     low direct value, high strategic value as the enabling seam.)
   - **Phase B ⬜ — log scale (spike done ✅, ready to implement).** The blocker —
     pyqtgraph's `setLogMode` doesn't transform our bare render items — is resolved:
     the spike proved **Approach A** (pre-`log10` the data in the renderers +
     `AxisItem.setLogMode` for ticks; one consistent `10**` de-log at each event
     boundary). Findings, the R1 normalization map, edge-case policy, and effort are in
     [`axis-surface-feasibility.md`](axis-surface-feasibility.md) §10. matplotlib needs
     **no** coordinate work (`get_xlim` stays data-space under log); webengine needs R1
     only in its relayout/restore path; pyqtgraph is the bulk (~120–150 LOC, bounded).
     Remaining choice is rollout shape — **all-at-once** (log on all 3 backends, keeps
     "renders identically") vs **staged B1→B2** (mpl/web first, pyqtgraph gated to
     linear, then Approach A). Sub-decisions: non-positive policy (drop+warn), include
     `symlog` (mpl-only, exercises gating), datashader gate.
   - **Phases C–D** — declarative limits / invert / aspect, then a backend-agnostic
     tick-format vocabulary (`si | percent | datetime | fixed:N`).
   - Also unlocks Datashader `logx` / `logy`.
4. **Raster selection** — pixel → source rows for brush/linked-select on datashaded views
   (builds on the [D46] hover reverse-lookup).
5. **Remaining Datashader coverage** — ✅ **shipped (native)** — raster legends/colorbars,
   theme-driven colors, and a wider aggregation surface (`Scatter.agg`), via the
   aggregate/shade split ([D47]–[D50], `milestone-datashader-coverage.md`). Remaining:
   webengine raster legends (no webengine legends yet), multi-agg `summary`, line styling,
   gridded regrid (`capabilities-gaps.md` §1).

Deferred / optional: webengine W5.2 binary transport; HoloViews adapter L2 (bidirectional
streams) + the `.qtviz` accessor; Studio (Phases 7–9, post-1.0).
