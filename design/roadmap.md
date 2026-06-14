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
| 0 | rename · CI · spikes | ◑ rename ✅; spikes folded into Phase 1; **CI matrix still open** |
| 1 | core compose + pyqtgraph | ✅ |
| 2 | matplotlib backend | ✅ |
| 3 | HoloViews adapter | ⬜ not started (independent; Spike-P2 gated) |
| 4 | reactive + Datashader | **Datashader ✅**; reactive `Signal` ⬜ |
| 5 | data layer + webengine | **lazy adapters ✅** (dask/xarray/zarr); Parquet/DuckDB/SQL sources ⬜; webengine rehome ⬜ |
| 6 | release `0.1` | ⬜ |

**Recommended next order** (detail in `development-plan.md` §8): finish Datashader
coverage [D22] → reactive signals → data sources (Parquet/DuckDB) → HoloViews
adapter → webengine rehome → release. The phase tables below are retained as the
original estimate/acceptance reference, with status annotated inline.

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

### Phase 0 — Pivot prep + spikes (1 month) · ◑ rename done; CI matrix open

| Deliverable                                                | Acceptance                                          |
|------------------------------------------------------------|------------------------------------------------------|
| Rename `qtwebplot` → `qtviz`; old code moves under `backends/webengine` | Tests pass on new paths; old import path errors with hint |
| GitHub Actions CI matrix (macOS/Lin/Win × 3.11/3.12/3.13)  | All current tests pass on all platforms              |
| PyPI/GitHub names reserved (`qtviz`, `qtvizstudio`)         | Reservations confirmed                               |
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

### Phase 3 — HoloViews adapter (1 month) · ⬜ not started

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

### Phase 4 — Reactive + Datashader (1.5 months) · ◑ Datashader done; reactive open

> **Status.** The Datashader rows below (✅) shipped — but *as a backend-agnostic
> pipeline transform* (Scatter→Image in `resolve_node`), not the pyqtgraph-only
> `pg.ImageItem` path this table assumed; it works on every backend, out-of-core,
> with debounced viewport re-aggregation [D18–D21, `milestone-phase4-datashader.md`].
> The reactive `Signal` rows (⬜) are the remaining half of this phase.

| Deliverable                                          | Acceptance                                           | Status |
|------------------------------------------------------|-------------------------------------------------------|--------|
| `qtviz.reactive` — Signal / derived / effect         | <500 LOC, no async, dispose semantics                | ⬜ |
| `Element(data=signal(...))` reactive binding          | Changing the signal re-renders the element          | ⬜ |
| Linked brushing across views via signals              | Brush on one Scatter filters another Element         | ⬜ |
| `ext.datashader` integration                          | `Scatter(table, scale="datashader")` aggregates out-of-core; backend-agnostic raster | ✅ |
| Viewport-driven re-aggregation                        | Pan/zoom triggers debounced re-aggregation          | ✅ |
| Crossfilter rewrite                                    | `examples/dashboard_crossfilter.py` rewritten in ≤80 LOC using signals + native Scatter | ⬜ (needs reactive) |

**Acceptance milestone.** Reactive crossfilter dashboard, 10M rows,
pyqtgraph backend, Datashader for any single view that exceeds 1M
visible points. ≤80 LOC.

**Risks.** Datashader → pg.ImageItem rasterization round-trip latency.
Mitigation: spike during Phase 0; if >100 ms typical, drop to
mpl-rendered Datashader image.

### Phase 5 — Data layer + webengine backend rehome (2 months) · ◑ lazy adapters done; sources + webengine open

> **Status.** The lazy-first *adapter* layer this phase implied is already built —
> container-agnostic `DataRef` adapters for dask/xarray/zarr (wrap existing
> in-memory lazy objects), out-of-core and off-thread [D1, D17, `milestone-data-core.md`].
> What remains here is the *source* layer below (`DataSource` reading Parquet/DuckDB/
> SQL/CSV from disk or a DB) and the **webengine backend rehome** — both still ⬜.

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

### Phase 6 — Library 0.1 release (1 month) · ⬜ not started

| Deliverable                                          | Acceptance                                           |
|------------------------------------------------------|-------------------------------------------------------|
| Doc site complete                                     | Tutorial, gallery (10 examples), API reference       |
| `qtviz 0.1.0` on PyPI                                 | `pip install qtviz` works                            |
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
0 ─→ 1 (pyqtgraph) ─→ 2 (mpl) ─→ 3 (hv adapter) ─→ 4 (reactive+datashader) ─→ 5 (data+webengine rehome) ─→ 6 (lib 0.1)
          │
          └─ halt if pyqtgraph composition is impractical (Spike P1 fails)
```

Spike P2 (HoloViews adapter feasibility) is the gate for Phase 3, not
the whole project — if it fails, drop Phase 3, ship native-only.

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

## 8. What to do first

1. Confirm the recommendations in §7 (or override).
2. Run the four Phase 0 spikes (P1: pyqtgraph composition; P2: HoloViews
   adapter prototype; P3: mpl HoloViews wrap; D1: 1M scatter perf).
   Total ~10 days.
3. Rename the package and set up CI matrix (parallel to spikes).
4. After spikes pass: begin Phase 1 with `qtviz.core.element` and the
   pyqtgraph backend's Scatter.

If P1 fails (pyqtgraph can't carry the composition load) the whole
pivot is questionable — re-plan. If only P2 fails (HoloViews adapter is
impractical), drop Phase 3 and ship native-only. P3 and D1 are
performance gates that influence scope but don't kill the plan.
