# Design: multi-visualization support

> **Status: realized natively (M5).** This was the WebEngine-era exploration of
> multi-plot support; its core ideas — one-plot and N-plots as a continuum,
> mixed-backend grids/tabs/docks/splitters, backends opting into any "native
> multi" capability — shipped in the native qtviz `Layout` system
> (`core/compose.py` + `core/_host.py`, `CompositeRenderHandle`). Retained for the
> design rationale; the WebEngine framing below is superseded by the Backend
> protocol (`spec.md` §2, `development-plan.md` §3).

## 1. Goal

Make it cheap to render and manage many visualizations simultaneously, each
presented in its own widget surface (cells in a grid, tabs, docks). The
architecture should:

- Treat "one plot" and "N plots" as a continuum, not different worlds.
- Let users mix backends freely (one Plotly + three Bokeh in the same grid).
- Stay backend-agnostic at the core — backends opt in to any "native multi"
  capability they have.
- Scale gracefully: 2 plots feels frictionless, 30 plots is still tolerable.

## 2. Motivating use cases

| Case | Shape                                              | Coupling                              |
|------|----------------------------------------------------|---------------------------------------|
| A    | Side-by-side comparison (A vs B)                   | None                                  |
| B    | Sensor dashboard (6–12 small live plots)           | Shared time axis, maybe linked brush  |
| C    | Variant grid (same dataset, different views)       | Shared data source                    |
| D    | Tabbed report (15+ plots, only one visible)        | None                                  |
| E    | Drill-down (top plot drives detail plots)          | Selection on A populates B and C       |
| F    | Auto-generated batch (user iterates a study)       | Dynamic — plots come and go            |

Cases A, D, F want independence — separate widgets, no coordination.
Cases B, C, E want either *backend-native* coordination (Plotly subplots,
Bokeh `gridplot`) or *Python-side* coordination (signal a from view A drives
verb b on view B).

## 3. Design dimensions

Anything we ship has to answer all four:

1. **Creation** — how a user constructs N visualizations.
   - Static list at construction time.
   - Dynamic add/remove after construction.
   - Mix (start with a list, add more later).
2. **Layout** — how they are presented in Qt.
   - Grid (`QGridLayout`).
   - Tabs (`QTabWidget`).
   - Splitter (`QSplitter`).
   - Free-floating windows.
   - Dockable panels (`QDockWidget`).
3. **Lifecycle** — when each view is built/torn down.
   - Eager: all built up-front.
   - Lazy: built on first visibility (useful for tabs, dock with hidden panels).
   - Recycled: pool of views reused for changing content.
4. **Coordination** — whether plots share state/events.
   - None (independent — the default).
   - Shared theme / sizing config.
   - Linked events (selection in A → restyle in B).

## 4. Three implementation strategies

### Strategy A — Layout helpers around independent `PlotView`s

What it is: N `PlotView` widgets, each with its own `WebBridgeView` and
backend, composed by a Qt layout. Ships as small composition helpers.

**Components:**

```python
qtwebplot.PlotGrid(backends, cols=2, parent=None)
qtwebplot.PlotTabs({"label": backend, ...}, parent=None)
qtwebplot.PlotSplitter(backends, orientation=Qt.Horizontal, parent=None)
```

Each helper:
- Builds one `PlotView` per backend.
- Exposes `views` (`list[PlotView]`) and `backends` (`list[PlotBackend]`)
  properties for reach-through.
- Supports `add(backend, ...)` / `remove(index)` for dynamic cases (F).
- Optional `lazy=True` for tabs/dock: build the view only when its panel
  first becomes visible.

**Tradeoffs:**

- ✅ Full isolation. One plot misbehaving doesn't take down the others.
- ✅ Trivial to mix backends.
- ✅ Builds on what we already have — backends, bridge, runtime all unchanged.
- ❌ Memory: each `QWebEngineView` is its own page (~30–60 MB resident).
  Ten plots ≈ 300–600 MB. Twenty starts to hurt on small machines.
- ❌ Each page reloads its plotting JS runtime (Plotly is ~3 MB compressed).
  Browser caches help across reloads of the same backend, but cold start
  is still N × per-page-load time.
- ❌ Cross-plot coordination is Python-side only — link via signal wiring
  in user code, not a shared JS surface.

### Strategy B — `MultiPlotView`: one bridge, many backends

What it is: a single `WebBridgeView` hosting N backends multiplexed into
one page. Each backend renders into its own `<div>` slot; the bridge routes
events to the right backend by slot ID.

**Required changes:**

1. `PlotBackend` gains an optional `to_fragment(slot_id) ->
   FragmentBundle(head, body, init_script)`. Backends that support
   multi-host implement it; backends that don't fall back to "I need my own
   page" (`MultiPlotView` either rejects them or wraps them in an `<iframe>`).
2. `WebBridgeView` (or a new `MultiPlotView` subclass) composes fragments:
   - Deduplicates `head` includes (so Plotly's JS loads once).
   - Lays out bodies in a grid/flex/CSS layout.
   - Runs init scripts in order.
3. Per-slot JS namespace: each backend's runtime addresses a slot-scoped
   `qtwebplot.plots[slot_id]` proxy instead of the global `qtwebplot`.
4. Event routing: messages emitted from slot X arrive at Python tagged
   with `slot_id` in the payload (or name prefix). The composite view
   demultiplexes and re-emits as `backends[slot_id].received`.

**Tradeoffs:**

- ✅ One Chromium process, one runtime. Memory savings of ~10× for many
  small plots.
- ✅ Cross-plot coordination is natural in JS (one bridge, one document).
- ✅ Faster cold start — one page load instead of N.
- ❌ Substantial new contract for backends (`to_fragment`). Plotly is
  straightforward (`to_html(full_html=False)`); Bokeh requires
  `bokeh.embed.components`; arbitrary backends need explicit support.
- ❌ One bad plot crashes the whole page. Fault isolation lost.
- ❌ Backend authors now have two flavors of `to_html` to think about.
- ❌ CSS leakage between backends if they ship their own styles.
- ❌ Initial implementation complexity is meaningful — slot management,
  message routing, fragment composition, asset deduplication.

### Strategy C — Backend-native multi

What it is: use the library's own multi-plot constructs and present them
as a single backend instance.

- Plotly: `plotly.subplots.make_subplots(...)` returns one `Figure`.
- Bokeh: `bokeh.layouts.gridplot([[p1, p2], [p3, p4]])` returns one model.
- HoloViews: `a + b`, `a * b` compose into one `Layout` / `Overlay`.

**Tradeoffs:**

- ✅ Zero new infrastructure. Already supported today — pass the composed
  figure to `PlotlyBackend(...)` or `BokehBackend(...)`.
- ✅ Library-native coordination (shared axes, linked crossfilter, etc.).
- ❌ One backend instance → one event stream → can't naturally distinguish
  "user clicked the third subplot" without parsing trace indices.
- ❌ All plots must be the same backend.
- ❌ Heterogeneous layouts (mixed sizes, gaps) require fighting the
  library's layout primitives.

## 5. Recommendation

**Ship Strategy A now. Document Strategy C. Defer Strategy B.**

Reasoning:

- Strategy A solves cases A, D, F outright and handles B, C, E with
  Python-side signal wiring (we can document patterns once we have a real
  use case in front of us).
- Strategy A is small (~150 LOC for the three helpers + lazy loading),
  builds on what's already shipped, and ships without changing the
  backend contract.
- Strategy C is "already supported" — we just need a docs section and one
  example.
- Strategy B is genuinely useful but expensive. The 10× memory savings
  matter at scale (20+ plots) and for dashboard apps. We should build it
  *after* someone has hit the wall with Strategy A, not before — when we
  know exactly what their composition / coordination needs are, the API
  will be sharper. Premature Strategy B forces backend changes that may
  not match the actual demand.

## 6. API sketch — Strategy A

### `PlotGrid`

```python
class PlotGrid(QWidget):
    def __init__(
        self,
        backends: Sequence[PlotBackend] = (),
        *,
        cols: int = 2,
        spacing: int = 4,
        parent: QWidget | None = None,
    ) -> None: ...

    # views[i] / backends[i] correspond by index.
    @property
    def views(self) -> list[PlotView]: ...
    @property
    def backends(self) -> list[PlotBackend]: ...

    def add(self, backend: PlotBackend) -> PlotView: ...
    def remove(self, index: int) -> None: ...
    def clear(self) -> None: ...

    # Reach-through helpers
    def view_at(self, row: int, col: int) -> PlotView | None: ...
```

### `PlotTabs`

```python
class PlotTabs(QWidget):
    def __init__(
        self,
        backends: Mapping[str, PlotBackend] | Sequence[tuple[str, PlotBackend]] = (),
        *,
        lazy: bool = True,
        parent: QWidget | None = None,
    ) -> None: ...

    @property
    def views(self) -> list[PlotView]: ...   # built views; lazy tabs absent until visited
    @property
    def backends(self) -> list[PlotBackend]: ...

    def add(self, label: str, backend: PlotBackend) -> int: ...   # returns tab index
    def remove(self, index: int) -> None: ...
    def view_for(self, label: str) -> PlotView | None: ...
```

`lazy=True` (default) only builds a tab's `PlotView` the first time the
user selects it. Memory matters most for tabs — eager mode (`lazy=False`)
is the escape hatch.

### `PlotSplitter`

```python
class PlotSplitter(QSplitter):
    def __init__(
        self,
        backends: Sequence[PlotBackend] = (),
        *,
        orientation: Qt.Orientation = Qt.Horizontal,
        parent: QWidget | None = None,
    ) -> None: ...
```

Plain pass-through of `QSplitter` with auto-`PlotView` wrapping.

## 7. Phased plan

| Phase | Scope                                                    | Files                                                            | Est. LOC |
|-------|----------------------------------------------------------|------------------------------------------------------------------|----------|
| M0    | `PlotGrid` (eager only) + example                        | `qtwebplot/layouts.py`, `examples/grid.py`                       | ~120     |
| M1    | `PlotTabs` (eager + lazy) + example                      | `qtwebplot/layouts.py`, `examples/tabs.py`                       | ~80      |
| M2    | `PlotSplitter` + smoke tests for all three               | `qtwebplot/layouts.py`, `tests/test_layouts_gui.py`              | ~60      |
| M3    | Docs: "multiple visualizations" page covering A and C    | `design/architecture.md` integration                              | docs only |

Strategy B comes only if a real workload hits Strategy A's memory ceiling.

## 8. Cross-cutting decisions

These apply to all helpers and need to land consistently:

- **Where the code lives:** new module `qtwebplot/layouts.py` exporting
  `PlotGrid`, `PlotTabs`, `PlotSplitter`. Top-level re-exports in
  `qtwebplot/__init__.py`. The flat namespace keeps the API discoverable.
- **Backend instances vs. backend factories:** the helpers take *instances*.
  A user who wants per-cell deferred construction wraps in `lazy=True` (for
  tabs) or constructs the backend at `add(...)` time.
- **Sizing:** each `PlotView` already fills its parent. Helpers add no
  sizing logic of their own — defer to the layout (`QGridLayout`,
  `QTabWidget`, `QSplitter`).
- **Bulk ops:** helpers expose `views` for users to walk and apply common
  configuration (e.g., `for v in grid.views: v.enable_debug_log()`).
  No bulk methods on the helpers themselves — adding them invites a
  "what about set_throttle for all" / "what about export_png for all"
  parade that bloats the API. The `views` reach-through is cleaner.
- **Theming:** if/when `Theme` lands, helpers accept a `theme=` kwarg
  applied to every contained view. Until then, users apply per-view.

## 9. Open questions for review

1. **Should the helpers live in `qtwebplot.layouts` (recommended) or be
   top-level (`qtwebplot.PlotGrid`)?** Lean toward submodule + selective
   top-level re-export (`PlotGrid`, `PlotTabs` re-exported; `PlotSplitter`
   only in submodule because it's a thinner wrapper).
2. **Lazy by default for tabs?** Recommend yes — matches user expectations
   (a 30-tab dashboard shouldn't allocate 30 WebEngine pages at startup).
3. **Should `PlotGrid` support dynamic resizing (drag handles between
   cells)?** Recommend no for v1 — that's `QSplitter`'s job. Users who
   need it use `PlotSplitter` or compose `QSplitter`s themselves.
4. **Should helpers offer linked-event sugar — e.g.,
   `grid.link("hover", source=0, target=[1,2,3])`?** Recommend no. Once
   you wire one of these you start needing a coordination DSL; better to
   document the "connect signals between backends" pattern in the docs
   and let users do it explicitly until we see what they actually need.
5. **Closing/destroying behavior:** when a helper is closed, should its
   contained `PlotView`s be explicitly torn down? Recommend explicit
   `clear()` on `closeEvent` to drop WebEngine pages promptly — they
   leak otherwise.
6. **Backend-native multi (Strategy C):** is documenting it enough, or
   do you want a tiny `qtwebplot.subplots(backends, layout="grid")`
   helper that picks the library-native composition path when all
   backends are the same library? Lean toward "docs only" for v1; the
   helper duplicates what the libraries already do well.

## 10. Decision points before implementation

If you sign off on Strategy A:

- Confirm #1 (location), #2 (lazy default), and #5 (close behavior).
- Confirm whether M0 starts with `PlotGrid` alone or `PlotGrid + PlotTabs`
  bundled.
- Anything in §6 (API sketch) you'd cut or add.

After that I'll implement M0 + an example, and we can validate the shape
on something concrete before M1/M2.
