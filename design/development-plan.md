# qtviz — development plan

> Sits between `spec.md` (the *how* — abstractions and interfaces) and
> `roadmap.md` (the *what / when* — phases and estimates). This doc is the
> *build*: how the components decompose, the contracts between them, the
> order we construct them in, and how each step is verified.
>
> Companion: `discussion-items.md` — the running record of tradeoffs and
> open questions to settle before/while building. Numbers like **[D3]**
> point at entries there.
>
> Depth follows the spec's gradient: concrete for Phase 0–2 (pyqtgraph +
> matplotlib), sketch for Phase 3+.

## 1. Design invariants

The architecture is correct only if all of these stay true. They are the
acceptance criteria for *every* design decision below; if a proposed change
breaks one, the change is wrong.

1. **Elements are pure, immutable, Qt-free, value-hashed.** No Element (or
   Option/composition node) imports Qt or a backend. Equality/hash exclude
   `id` and fingerprint data refs (spec §2.1).
2. **Backends are registered, never imported by core.** Adding a backend
   touches only files inside that backend's directory (spec §7, §13).
3. **Negotiation is pure.** Choosing a backend per node requires no Qt and
   no rendering — only the registry's `supports()` + `capabilities`. It is
   unit-testable against stub backends with no `QApplication`.
4. **One GUI thread for all Qt mutation** (spec §2.14). Everything else is
   marshaled.
5. **One Element, one meaning, across backends.** Backends differ only in
   *declared* capabilities and *declared* degradations — never in silent
   behavior (spec §3.4).
6. **New invariant — the pure core imports without a `QApplication`.** The
   entire data/composition/negotiation layer must be importable and
   testable headless. Qt-coupling is confined to a named, enumerable set of
   modules (§2 below). This is what makes Tier‑1 tests fast and keeps the
   abstractions honest.

## 2. Component map

Each module has one responsibility and a small public surface. The split
that matters most for velocity is **pure core** (no Qt, Tier‑1 testable)
vs **Qt‑coupled**.

### Pure core (no `QApplication` needed)

| Module | Responsibility | Public surface | Depends on |
|--------|----------------|----------------|------------|
| `core/_immutable.py` | Frozen-by-convention mixin | `Immutable` (`_freeze`/`with_`/`_fields`/`_value_key`/eq/hash/repr) | — |
| `data/ref.py` | Container-agnostic handle | `DataRef`/`TabularRef`/`GriddedRef`, `Schema`, `GridData` | — |
| `data/registry.py` | Pluggable adapter registry | `DataAdapter`, `register_data_adapter`, `as_data_ref` | — |
| `data/adapters/*` | Per-container adapters | (registered) eager: dict/numpy/pandas/arrow; lazy later: xarray/zarr/dask | the lib (lazy import) |
| `core/color.py` | Canonical color | `Color`, `ColorSpec`, name table | PySide6 (lazy, `.qt()` only) |
| `core/palette.py` | Ordered colors + registry | `Palette`, `palettes.{register,get,list}` | `color` |
| `core/options.py` | Universal + container options | `Options`, `OverlayOptions`, `LayoutOptions` | `_immutable`, `color`, `palette` |
| `core/element.py` | Element base + id | `Element`, `_next_element_id` | `_immutable`, `data_ref` |
| `elements/*.py` | The 8 element types | `Scatter`…`Spread` | `element`, `color` |
| `core/theme.py` | Visual theme (migrated, §2.13) | `Theme` | `color`, `palette` |
| `core/capabilities.py` | Backend capability record | `Capabilities` (frozen dc) | — |
| `core/errors.py` | Error taxonomy (§6) | `QtvizError` + subclasses | — |
| `core/compose.py` | Composition + negotiation | `Overlay`, `Layout`, `*`/`+`, `negotiate`, `auto_negotiate` | `element`, `errors`, registry iface |
| `core/event.py` *(types half)* | Typed events | `Event`, `RangeEvent`… | — |

### Qt-coupled (Tier‑2 / `pytest-qt`)

| Module | Responsibility | Public surface | Depends on |
|--------|----------------|----------------|------------|
| `core/event.py` *(bus half)* | Delivery + throttle | `EventBus`, `Throttle`, `Disposable` | PySide6 (`QTimer`) |
| `core/threading.py` | GUI-thread discipline | `require_gui_thread`, `run_on_gui`, `Worker`, `is_gui_thread` | PySide6 |
| `core/backend.py` | The plug-in contract | `Backend` (Protocol), `RendererRegistry`, `RenderContext`, `RenderHandle`, `CompositeRenderHandle`, `ElementRenderer` | `event`, `threading`, `capabilities` |
| `core/_host.py` | Generic Qt layout host | `LayoutHost` → `CompositeRenderHandle` | `backend`, `compose`, PySide6 |
| `core/view.py` | User widget + lifecycle | `View(QWidget)` | `backend`, `compose`, `_host`, `event` |
| `backends/__init__.py` | Registry + lazy detection | `register`, `list_available`, `set_default_backend`, `set_backend_priority` | `backend`, impls |
| `backends/pyqtgraph/**` | Primary backend | (registered instance) | pyqtgraph, `backend`, `elements` |
| `backends/matplotlib/**` | Phase 2 backend | (registered instance) | matplotlib, … |
| `backends/webengine/**` | Phase 5 (rehomed qtwebplot) | (registered instance) | QtWebEngine, … |

> **Divergence from spec §13:** the plan splits `LayoutHost` out of
> `compose.py` into `core/_host.py`. Reason: `compose.py` must stay
> Qt-free (invariant 3, 6); `LayoutHost` builds `QSplitter`/`QTabWidget`.
> Keeping them in one module would drag Qt into the pure negotiation tests.

### Dependency direction (acyclic)

```
            _immutable        color
               │  ╲            │  ╲
          data_ref  ╲      palette  options
               │     ╲        │      │
            element ── elements      │
               │                     │
   capabilities│   errors   event(types)
            ╲  │   ╱           │
             compose (pure: negotiate/auto_negotiate, *, +)
                  │
   ┌──────────────┼──────────── Qt boundary ───────────────┐
   │            backend (Protocol, RenderHandle, registry)  │
   │              │        │                                │
   │    threading │   event(bus/throttle)                   │
   │            _host      │                                │
   │              ╲        │                                │
   │               view ───┘                                │
   │                 │                                      │
   │           backends/* (pyqtgraph, mpl, webengine)       │
   └────────────────────────────────────────────────────────┘
```

No arrow points upward; no backend points sideways at another backend.

## 3. Interface contracts (the seams)

The spec defines the types. This section names the **five seams** that
hold them together and the **four abstractions the spec implies but never
names** — the parts most worth getting right.

### 3.1 The five seams (restated tightly)

| Seam | Carrier | Rule |
|------|---------|------|
| Element → Backend | `RendererRegistry` (`type → ElementRenderer`) + `RenderContext` | Backend imports Element types to register; Element never imports backend. |
| Composition → Backend | `Backend.supports()` + `Capabilities` | `negotiate` reads only these; never constructs a widget. |
| View → Backend | `Backend.render(node) → RenderHandle` | View holds exactly one *root* handle (plain or composite). |
| Data → Element | `DataRef` (`snapshot`/`subscribe`/`fingerprint`) | Element stores a `DataRef`; renderer calls `snapshot()`. |
| Backend → App | `EventBus` (in `RenderContext`) + typed `Event`s | Renderers publish; `View.on` subscribes; delivery on GUI thread. |

### 3.2 The data layer — a pluggable, lazy-first subsystem (resolved [D1])

The decision on [D1]: **not** a thin columnar shim, but a data subsystem
shaped like the backend registry — because this library runs in
data-intensive settings where users bring xarray, zarr, and dask, and
out-of-core data must never be materialized just to draw a viewport. Full
contract in `spec.md` §2.1 + §6; the architecture-critical points:

- **Two shapes**, one contract: `TabularRef.series(name) -> 1-D ndarray`
  and `GriddedRef.grid(value) -> (2-D values, x, y)`. Renderers consume
  numpy via *named* resolution and never branch on the container.
- **Lazy-first.** Cheap metadata ops (`schema`/`size`/`extent`/`select`/
  `window`/`fingerprint`) are sync and GUI-safe; the single expensive op
  (`materialize`) runs on a Worker. The pipeline narrows
  (`select`+`window`, pushed down into dask/zarr) *before* it materializes,
  so only the visible slice is ever computed. This is the data-side reason
  the `materialize` pass [D3] exists.
- **Pluggable, not dependency-bound.** A `DataAdapter` registry mirrors the
  backend registry: optional adapters auto-register iff their library
  imports; third parties contribute via a `qtviz.data_adapters`
  entry-point. We ship the contract + eager adapters (dict/numpy/pandas/
  arrow); xarray/zarr/dask/`DataSource` are *one adapter file each*, added
  with **zero** changes to Element, renderer, negotiation, or View.
- **Escape hatch.** `native()` hands the underlying dask/pandas object
  straight to a scale strategy (Datashader) so big-data aggregation skips
  the dense-ndarray round-trip entirely.

This subsystem is pure (no Qt); only `materialize` of a lazy ref touches a
Worker. It is the data-side instance of invariant 2 (pluggable, additive).

### 3.3 New abstraction — `ViewState` (interaction portability) [D2]

Two operations must *not* throw away the user's zoom/pan/selection:
`handle.update(new_root)` (Phase 1 = full rebuild) and `view.set_backend()`
(cross-backend swap). Without a neutral carrier, a reactive update or a
backend switch silently resets the view to data bounds — a UX bug that
will surface immediately.

```python
@dataclass(frozen=True)
class ViewState:
    x_range: tuple[float, float] | None
    y_range: tuple[float, float] | None
    selection: list[int] | None

class RenderHandle:
    def capture_state(self) -> ViewState: ...
    def restore_state(self, s: ViewState) -> None: ...
```

`update` and `set_backend` capture before, restore after. Each backend
maps `ViewState` to/from its native ranges. This is additive to the spec's
`RenderHandle` and should be folded in — see **[D2]**.

### 3.4 New abstraction — the `materialize` pass [D3]

In-memory `snapshot()` is sync; a Phase 5 `DataSource.snapshot()` returns a
`Future`. Renderers must never see a Future. So the render pipeline gains a
**materialization phase** on the GUI thread, *between* negotiation and
rendering:

```
set_root → negotiate(root) → materialize(root) → backend.render(materialized)
                                   │
                                   └─ lazy refs: kick Worker, show placeholder,
                                      re-enter render() when the Future resolves
```

In Phase 1 `materialize` is the identity function (all refs are in-memory).
It exists in the pipeline from day one so Phase 5 slots in without
reshaping `View`. Placement and re-entrancy are **[D3]**.

### 3.5 Error taxonomy

One base, caught broadly; specific subclasses, raised precisely. Collected
from the spec's scattered error names plus the gaps.

```python
class QtvizError(Exception): ...
class NegotiationError(QtvizError): ...
class IncompatibleOverlayError(NegotiationError): ...   # §2.3, §3.2
class UnsupportedElementError(NegotiationError): ...     # §3.2
class NoBackendForError(NegotiationError): ...           # §3.3
class BackendNotAvailableError(QtvizError): ...          # §3.6 (install hint)
class RendererMissingError(QtvizError): ...              # registry miss
class AdapterError(QtvizError): ...                      # from_holoviews (§8)
```

Every raise carries an actionable message (supported-backends list, install
hint, etc.) — the spec already models the tone.

## 4. Build sequence

The spec's §13 lists files bottom-up; building strictly bottom-up means
nothing *runs* until the last step. Instead we drive a **walking skeleton**
— one element end-to-end through every layer first — then widen (more
elements) and deepen (events, composition, switching). Each milestone is a
shippable, tested increment.

> **Status (commit 97b2e14):** M0 ✅ · M1 ✅ · M2 ✅ · M3 ✅ (all 8
> pyqtgraph renderers, theme, handle, ViewState) · **M4 next** (interaction —
> detailed plan in `milestone-m4-interaction.md`). Re-sequenced tail:
> **M4 → M6 (matplotlib) → M5 (mixed-backend host)** — M5's `LayoutHost`
> only becomes testable once a second backend exists.

### M0 — Walking skeleton · `View(Scatter) → pyqtgraph → window`
- **Components:** minimal `Immutable`; `as_data_ref` + one eager adapter
  (dict/pandas → `TabularRef`);
  `Element` + `Scatter` (x/y only); `Backend` protocol (`render` only);
  pyqtgraph backend with a single Scatter renderer; `View` (no switching,
  no events, no theme).
- **Deliverable:** `View(Scatter(df, x="a", y="b")).show()` draws points.
- **Verifies:** the Element→registry→renderer→handle→widget seam holds.
- **Why first:** every later milestone is "fill in" against a proven spine.

### M1 — Pure data model + data layer (no Qt)
- **Components:** full `Immutable` (`with_`/`_value_key`/eq/hash + the
  round-trip conformance test); the **data layer** — `DataRef`/`Tabular
  Ref`/`GriddedRef` contract, `DataAdapter` registry, the four eager
  adapters (dict/numpy/pandas/arrow), `Schema`, `fingerprint`,
  `materialize`=identity, the cheap `select`/`window` no-ops; `Color`/
  `Palette`/registry; `Options`/`OverlayOptions`/`LayoutOptions`; all 8
  Element types with **schema-validated** field names; `Theme` migration
  (§2.13).
- **Deliverable:** the whole pure model + container-agnostic data binding,
  exercised headless.
- **Verifies:** Tier‑1 suite — immutability, value-equality across
  array-backed elements, `with_` round-trips, validation errors, **and the
  data-adapter conformance suite (§5.3) for the eager adapters** (same
  Element → same `series`/`grid` output through dict/pandas/arrow/numpy).
- **Note:** lazy/gridded adapters (xarray/zarr/dask) are deferred to the
  reactive/data phases (4–5) but the contract they satisfy is frozen here —
  if a lazy adapter later forces a change to `DataRef`, this milestone got
  the abstraction wrong.

### M2 — Composition & negotiation (pure)
- **Components:** `Overlay`/`Layout` + `*`/`+` operators; `Capabilities`;
  `negotiate`/`auto_negotiate`; error taxonomy; the auto-Overlay
  "supports-all-children" fix **[D4]**.
- **Deliverable:** given stub backends, any node tree resolves to a backend
  per node, or raises precisely.
- **Verifies:** Tier‑1 — precedence (Element>Composition>View>Global),
  Overlay coherence, auto collapse, unsupported-element errors. **No Qt.**

### M3 — Backend protocol + pyqtgraph breadth
- **Components:** `RendererRegistry`, `RenderContext`, `RenderHandle`
  (+ `capture/restore_state` [D2]); pyqtgraph renderers for all 8 elements;
  `_theme` (apply migrated Theme); Overlay (one ViewBox); single-backend
  grid Layout via `GraphicsLayoutWidget` with `link_x/link_y`.
- **Deliverable:** static multi-element, multi-panel pyqtgraph rendering.
- **Verifies:** Tier‑2 + the **backend conformance suite** (§5.3) green for
  pyqtgraph.

### M4 — Events + interaction
- **Components:** `core/threading.py` (+ `@require_gui_thread` enforcement
  test); `event` bus/throttle; pyqtgraph `_events` (range/pick/select/
  hover/tap); `View.on`.
- **Deliverable:** brush a scatter → `SelectEvent` fires; zoom → throttled
  `RangeEvent`.
- **Verifies:** Tier‑2 event tests; throttle timing; off-thread guard
  raises.

### M5 — View lifecycle + mixed-backend host
- **Components:** `set_root`/`set_theme`/`set_backend` (atomic, state-
  preserving via [D2]); subscription registry (survives switch, §2.10/Q-K);
  `LayoutHost` + `CompositeRenderHandle` (exercised pyqtgraph-only:
  splitter/tabs/dock); `backends/__init__` registry + lazy detection.
- **Deliverable:** the roadmap **Phase 1 gate** — 3-panel dashboard
  (Scatter + Histogram + Curve), shared X, linked brushing, `Theme.dark()`,
  < 60 LOC, 100% pyqtgraph.
- **Verifies:** the gate example runs; conformance suite still green;
  subscription survives a (pyqtgraph→pyqtgraph) re-render.

### M6 — matplotlib backend (the real test of the design — Phase 2)
- **Components:** `backends/matplotlib/**` — `FigureCanvasQTAgg` host,
  8 renderers, `_events` bridge, `_theme` via rcParams; `CompositeRender
  Handle` now meaningfully mixed (pyqtgraph + mpl panes).
- **Deliverable:** same dashboard, `set_backend("matplotlib")`, renders.
- **Verifies:** matplotlib passes the *same* conformance suite; a Layout
  with one pyqtgraph and one mpl pane renders and emits a merged event
  stream. **If adding mpl required editing any file outside
  `backends/matplotlib/`, the abstraction failed — that diff is the
  design's correctness check (spec §13).**

> M0–M5 fit inside roadmap Phase 1 (2.5 mo); M6 is Phase 2 (1.5 mo).
> Phases 3+ (HoloViews adapter, reactive/Datashader, data/webengine
> rehome) keep the spec's sketch depth and get their own plan when their
> gate opens.

## 5. Verification strategy

Four tiers, cheapest first. This section is the spec for the **benchmarks**
we build next — the conformance suite (§5.3) and perf harness (§5.4) are
the concrete deliverables of that effort.

### 5.1 Tier 1 — pure unit (no Qt)
Runs on the pure core with no `QApplication`; milliseconds; the bulk of
coverage. Targets: immutability + value identity (incl. array-backed),
`with_` round-trip, color/palette parsing, option validation, element
validation, `negotiate`/`auto_negotiate` against **stub backends**.

### 5.2 Tier 2 — `pytest-qt` (offscreen)
`QT_QPA_PLATFORM=offscreen`. Backend rendering, `View` lifecycle, event
delivery + throttle timing, threading guards. Carries over the existing
`pytest-qt` harness used today for the bridge.

### 5.3 Tier 3 — backend conformance suite (the keystone)
One parametrized suite every backend must pass — what keeps three backends
honest as the surface grows (the idea floated in `future.md`). Sketch:

```python
@pytest.fixture(params=list_available())          # one run per backend
def backend(request): return request.param

ELEMENT_FIXTURES = {Scatter: make_scatter, Curve: make_curve, ...}

def test_renders_each_supported_element(backend, qtbot):
    for et, make in ELEMENT_FIXTURES.items():
        if not backend.supports(et): continue
        h = backend.render(make(), theme=Theme.light())
        assert h.widget is not None
        h.dispose()

def test_capabilities_are_internally_consistent(backend): ...
def test_required_options_honored(backend): ...
def test_unsupported_recommended_warns_once(backend, caplog): ...
def test_declared_events_fire(backend, qtbot): ...      # only the declared ones
def test_state_roundtrip(backend, qtbot): ...           # capture→restore [D2]
def test_each_declared_export_writes_a_file(backend, tmp_path): ...
```

Adding a backend = make the suite pass. Nothing else certifies it.

**Adapter variant.** The same idea certifies the data layer: parametrize an
equivalent fixture set over `list_data_adapters()` and assert the *same*
Element produces byte-identical `series`/`grid` output through every
adapter that can express the test data (dict ≡ pandas ≡ arrow ≡ numpy for a
tabular fixture; ndarray ≡ xarray ≡ zarr for a gridded one). Plus
laziness invariants: `select`/`window` on a lazy fixture must not trigger a
compute (assert via a counting/mock scheduler), and `materialize` must
return an eager ref. This is the executable form of "adding a container is
one adapter file."

### 5.4 Tier 4 — performance benchmarks
Gate scale claims, not correctness. From roadmap: **D1** 1M-row scatter
pan/zoom ≥ 30 FPS, brush < 16 ms; Datashader→`ImageItem` round-trip
(< 100 ms target, Phase 4); existing `tools/bench_bridge.py` for the
webengine path. Tracked over time to catch regressions.

### 5.5 CI matrix
macOS/Linux/Windows × Py 3.11/3.12/3.13 (roadmap Phase 0). Tier 1 +
Tier 2(offscreen) + ruff on every PR; Tier 4 on a schedule/manual.

## 6. Cross-cutting concerns

- **Threading enforcement.** `@require_gui_thread` wraps every renderer and
  the `RenderHandle`/`Backend`/`View` mutators (spec §2.14). A test asserts
  off-thread calls raise. Cost/strictness is **[D5]**.
- **Logging.** One namespaced logger (`qtviz`). Auto picks, degraded
  options, missing optional backends → INFO once. No telemetry (roadmap §7).
- **Packaging & rename.** `qtwebplot` → `qtviz`, src-layout; webengine code
  rehomes under `backends/webengine/`; `qtwebplot` import shim warns for
  two releases (roadmap Phase 0/6). Physical move strategy is **[D6]**.
- **Public API surface.** `import qtviz` exposes: the 8 elements, `Overlay`/
  `Layout`, `View`, `Theme`, `Color`, `Palette`, `palettes`, `Options`,
  `threading`, `set_default_backend`/`set_backend_priority`,
  `backends.list_available`, and (Phase 3) `from_holoviews`. Pin this list
  before M5 so docs/tests target a stable namespace.

## 7. Milestone → roadmap mapping

| Milestone | Roadmap phase | Gate it serves |
|-----------|---------------|----------------|
| M0 | Phase 0 spike P1 / Phase 1 start | spine proven |
| M1–M2 | Phase 1 | pure model + composition |
| M3–M4 | Phase 1 | pyqtgraph breadth + interaction |
| M5 | Phase 1 | **3-panel dashboard gate** |
| M6 | Phase 2 | **second backend = design proof** |
| (later) | Phase 3–6 | adapter, reactive, data, release |

## 8. What's next

1. Review this plan + `discussion-items.md`. [D1] (the data layer) is
   resolved and folded into spec §6; the remaining **[D#]** are accepted
   with a revisit flag, so nothing else blocks starting.
2. Build the **benchmarks**: the Tier‑3 conformance suite skeleton and the
   Tier‑1 fixtures — these become the executable acceptance criteria the
   implementation is written against.
3. Begin M0 once the conformance suite can express its acceptance.
