# qtviz — design specification

> Companion to `roadmap.md` (phases/timeline) and `native-pivot-research.md`
> (why three backends). This doc is the *how* — concrete abstractions
> someone could start implementing from.
>
> **Centerpiece**: the Backend system. Every other abstraction is shaped
> by the requirement that the same `Element` renders cleanly through
> `pyqtgraph`, `matplotlib`, and `webengine`, that users can switch
> backends at runtime, and that adding a fourth backend later does not
> require touching existing ones.

## 0. Status

Two axes: how deeply this doc specs each area, and what is **built** in
`src/qtviz` today. The build order diverged from the original phase numbering —
the data layer and Datashader were pulled forward, ahead of the HoloViews adapter
and reactive signals (see the as-built note below and `roadmap.md` §0).

| Area                                                    | Spec depth | Built |
|---------------------------------------------------------|------------|-------|
| Core model · 8 elements · composition (`*` / `+`)       | concrete   | ✅    |
| pyqtgraph backend                                       | concrete   | ✅    |
| matplotlib backend                                      | concrete   | ✅    |
| Interaction — typed events, brushing, linked axes       | concrete   | ✅    |
| Mixed-backend layouts (host + composite handle)         | concrete   | ✅    |
| Data layer — accessors + lazy adapters (dask/xarray/zarr) | concrete | ✅    |
| Datashader — big-data raster + viewport re-aggregation  | concrete   | ✅    |
| HoloViews adapter                                       | sketch     | ⬜    |
| Reactive `Signal` binding                               | sketch     | ⬜    |
| Data sources — Parquet / DuckDB / SQL                   | sketch     | ⬜    |
| webengine backend rehome                                | sketch     | ⬜    |
| Release `0.1`                                           | scaffold   | ⬜    |

**As-built deviations from this spec** (each ratified in `discussion-items.md`):

- **Data binding is functional.** A channel binds to an **accessor**
  (`str | Expression | Callable | ArrayLike`), not just a column name [D14].
  `Element.channels()` yields role-keyed accessors and the resolve pipeline turns
  them into arrays — generalizing the `x=/y=` column model in §5.
- **The data layer was built lazy-first now, not deferred to a later phase.**
  Container-agnostic adapters (dict/numpy/pandas/arrow eager; dask/xarray/zarr
  out-of-core) sit behind one `DataRef` contract; the adapter picks the shape,
  with `tabular()`/`gridded()` overrides [D1, D17].
- **Datashader is a backend-agnostic pipeline transform**, not a pyqtgraph-only
  `ImageItem` path: a huge Scatter is rewritten to an `Image` in `resolve_node`, so
  *every* backend renders it; dynamic re-aggregation rides a `RasterController` +
  a per-backend `RasterTarget` seam [D18–D21]. (Supersedes `roadmap.md` §7 #5.)

Detail deepens as we approach each unbuilt area. The built sections match the
implementation and are the gate: refactoring them later is expensive.

## 1. Layered architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  User API                                                         │
│  Element · Overlay · Layout · View · Theme · adapter.from_holoviews│
├──────────────────────────────────────────────────────────────────┤
│  Composition                                                      │
│  CompositionTree · BackendNegotiator · CapabilityMatcher          │
├──────────────────────────────────────────────────────────────────┤
│  Backend Protocol                                                 │
│  Backend · RendererRegistry · RenderHandle · EventBus · Threading │
├──────────────────────────────────────────────────────────────────┤
│  Backend implementations                                          │
│  pyqtgraph │ matplotlib │ webengine (rehomed qtwebplot)           │
├──────────────────────────────────────────────────────────────────┤
│  Substrate                                                        │
│  PySide6 · pyqtgraph · matplotlib · QtWebEngine                   │
└──────────────────────────────────────────────────────────────────┘
```

**Rules of dependency.**

- Composition imports Backend Protocol; never imports a backend impl.
- Backend impls import their substrate + Backend Protocol; never each other.
- User API imports Composition + Backend Protocol; never an impl directly.
- Backends are registered, not imported, at the entry point.

This is what allows a fourth backend to be added without touching any
existing file outside that backend's own directory.

## 2. Core abstractions

A choice runs through every type in this section: **plain Python classes
for user-extensible types (Element, Options, composition operators);
frozen dataclasses for internal data carriers (Capabilities,
RenderContext, Event subtypes)**. The pattern is deliberate. See §2.1
for the reasoning.

**Small type aliases** referenced throughout, declared once here:

- `ElementId = str` — a UUID4-derived string (Q-C).
- `Node = Element | Overlay | Layout` (also restated in §2.3).
- `Disposable` — a protocol with a single `dispose() -> None`; what
  `subscribe()` / `effect()` return.
- `BackendPrimitive = Any` — a backend's native object (`pg.ScatterPlotItem`,
  mpl `Line2D`, a JS trace handle); opaque to the core.
- `ConcreteData` — an eager ref's `native()` value (DataFrame / Arrow
  Table / ndarray); what backends touch only via `series()` / `grid()`.
- `Schema` / `GridData` — see §2.1 / §6: column-and-dim metadata, and the
  `(2-D values, x, y)` bundle a `GriddedRef.grid()` returns.

### 2.1 Element

`Element` is **pure declarative data**. It knows its data, mapping,
options, and identity. It knows *nothing* about rendering.

```python
class Element:
    """Base for all plottable elements. Plain Python class — deliberately
    not @dataclass — for maximum flexibility:

    - subclasses can validate inputs in __init__ with rich error messages
    - subclasses can expose computed properties (n_points, derived ranges, …)
    - subclass-of-subclass hierarchies don't require dataclass dance
    - subclasses can add methods beyond data accessors (.bind_signal, …)
    - per-element evolution adds properties without changing __init__ signature

    Immutability by convention: state is set in __init__; mutations
    return new instances via .with_(**changes). __setattr__ raises after
    self._freeze() at end of __init__."""

    # Per-Element classes declare these so the backend system can
    # validate options at composition time without inspecting the
    # renderer (see §3.4).
    REQUIRED_OPTIONS: tuple[str, ...] = ()
    RECOMMENDED_OPTIONS: tuple[str, ...] = ()

    _frozen = False

    def __init__(
        self,
        *,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ):
        self.backend_hint = backend_hint
        # ElementId is a UUID4-derived string — stable across processes
        # so Studio project files can persist Element references
        # (see Q-C, §11).
        self.id = id or _next_element_id()

    def _freeze(self) -> None:
        """Subclasses call this at the end of __init__ to enable immutability."""
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, key, value):
        if self._frozen:
            raise AttributeError(
                f"{type(self).__name__} is immutable; use .with_({key}=...)"
            )
        object.__setattr__(self, key, value)

    def _fields(self) -> dict[str, Any]:
        """All public attrs (non-underscore). Used by .with_() and __repr__."""
        return {k: v for k, v in vars(self).items() if not k.startswith("_")}

    def with_(self, **changes) -> Self:
        """Copy-on-write update — returns a new instance with the given
        attributes replaced. The `id` is preserved (stable identity across
        edits) unless explicitly overridden in `changes`."""
        fields = self._fields()
        fields.update(changes)
        return type(self)(**fields)

    def _value_key(self) -> tuple:
        """Value identity for __eq__/__hash__. Deliberately *excludes* `id`
        and represents data refs by a cheap hashable fingerprint rather
        than their contents:

        - `id` is a per-instance identity token, not a value. Omitting it is
          what makes two independently-constructed Elements with the same
          configuration compare equal and hash alike — without that, the
          negotiation cache and the (old_root == new_root) render
          short-circuit never hit, because every id() is unique.
        - raw arrays / DataFrames are *unhashable* and compare elementwise.
          Feeding them to hash()/== directly would make __hash__ raise and
          __eq__ return a non-bool. Each DataRef instead contributes
          `.fingerprint()` (§2.1 DataRef) — by default the identity of the
          underlying buffer, so equality means "same data object," never a
          deep value comparison of millions of rows."""
        items = []
        for k, v in sorted(self._fields().items()):
            if k == "id":
                continue
            items.append((k, v.fingerprint() if isinstance(v, DataRef) else v))
        return (type(self), tuple(items))

    def __eq__(self, other) -> bool:
        return isinstance(other, Element) and self._value_key() == other._value_key()

    def __hash__(self) -> int:
        return hash(self._value_key())

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self._fields().items())
        return f"{type(self).__name__}({items})"
```

A subclass example (full Scatter is in §5.1; this is the shape):

```python
class Scatter(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "size", "alpha", "marker")

    def __init__(self, data, *, x, y, color=None, size=None, marker="circle",
                 alpha=1.0, backend_hint=None, id=None,
                 pyqtgraph_use_opengl=False, matplotlib_rasterized=False):
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = data
        self.x, self.y = x, y
        self.color, self.size = color, size
        self.marker, self.alpha = marker, alpha
        self.pyqtgraph_use_opengl = pyqtgraph_use_opengl
        self.matplotlib_rasterized = matplotlib_rasterized
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self._freeze()
```

#### `DataRef` and `DataInput`

This library targets **data-intensive** work, so the data handle is not a
thin "give me the array" wrapper — it is the contract that lets the same
Element bind to a pandas DataFrame, an xarray dataset, or an out-of-core
**dask/zarr** array, and renders without ever materializing more than the
visible slice. Element *stores* a **`DataRef`**; the *user passes* any
**`DataInput`**, normalized by a pluggable adapter registry (§6) at
construction. The full data-layer architecture — shapes, adapters, the
container roadmap, laziness — is §6; this is the contract the rest of the
system sees.

```python
DataInput = Any           # anything a registered DataAdapter handles (§6):
                          # ndarray, dict, DataFrame, Arrow, xarray, zarr,
                          # dask, Signal, DataSource, or an existing DataRef.

@runtime_checkable
class DataRef(Protocol):
    """Uniform handle. Two refinements — TabularRef (named columns) and
    GriddedRef (named dims + coords) — plus a laziness flag so out-of-core
    data is narrowed before it is pulled. Architecture + adapters: §6."""

    is_lazy: bool

    # — cheap, sync, GUI-thread-safe: metadata only, never a full compute —
    def schema(self) -> Schema: ...               # names, dtypes, shape, shape-kind
    def size(self) -> int | None: ...             # row/element count; may estimate
    def extent(self, name: str) -> tuple[float, float] | None: ...
    def select(self, names: Sequence[str]) -> "DataRef": ...  # projection pushdown
    def window(self, **ranges) -> "DataRef": ...              # slice pushdown
    def fingerprint(self) -> Hashable: ...        # cheap hashable identity (§2.1)
    def subscribe(self, cb) -> Disposable: ...    # fire on change; no-op if static
    def native(self) -> Any: ...                  # escape hatch (e.g. hand to Datashader)

    # — expensive: Worker only, via the materialize pass (§6 / §2.14) —
    def materialize(self) -> "DataRef": ...       # → an eager ref; identity if eager

class TabularRef(DataRef):
    def series(self, name: str) -> "NDArray": ...                 # 1-D column → numpy
class GriddedRef(DataRef):
    def grid(self, value: str | None = None) -> "GridData": ...   # 2-D values + axes

def as_data_ref(data: DataInput) -> DataRef:
    """Walk the §6 adapter registry; wrap in the matching ref. Idempotent."""
```

`Element.__init__` runs `self.data = as_data_ref(data)`, then validates its
field names against `data.schema()` — cheap, since column/dim names are
metadata, no compute — so a typo'd `x="tmie"` raises at construction, not
at render. **Renderers only ever receive an *eager* ref** (`series`/`grid`
are sync): the render pipeline narrows (`select` + `window`) and
`materialize()`s lazy refs on a Worker first (§6, §2.14). `fingerprint()`
is adapter-specific — buffer `id()` for in-memory, `dask.base.tokenize` for
dask, a version counter for `Signal` (Q-O) — always cheap, never a compute.

**Names, not positions.** An Element's `x`/`y`/`z`/`color_by`/… are *names*
the ref resolves against whichever shape it is, so `x="time"` works whether
`time` is a DataFrame column or an xarray coordinate (§6.1). Point/line/
hist Elements need a tabular-resolvable ref; Image / Heatmap-from-grid need
a gridded one; the Element raises a clear error if its ref can't satisfy
the shape it needs.

Reactive subscription is orchestrated by `View`, not the Element
itself (§2.9).

#### Why immutable

The render pipeline compares `(old_root, new_root)`; cached
backend-negotiation results key off `Element` hashes; Signals deliver
new snapshots by replacing references. Mutable Elements would break
all three.

### 2.2 Options

Universal styling. Each backend translates these to native equivalents
or warns-and-degrades (§3.4).

```python
class Options:
    """Universal styling. Plain class so users can subclass for project
    presets (e.g., `class CompanyOptions(Options): ...`)."""

    _frozen = False

    def __init__(
        self,
        *,
        color: ColorSpec | None = None,
        alpha: float | None = None,
        palette: Palette | None = None,
        label: str | None = None,
    ):
        self.color = color
        self.alpha = alpha
        self.palette = palette
        self.label = label
        if alpha is not None and not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self._freeze()

    # same _freeze / __setattr__ / with_ / __eq__ / __hash__ / __repr__
    # as Element. Lifted via mixin in practice (see implementation notes).
```

Per-element options (`Scatter.marker`, `Curve.line_width`) live on the
Element subclass as fields, *not* on `Options`. Keep `Options` small
and universal.

### 2.3 Composition

Two operators — also plain classes for the same flexibility reasons:

```python
class Overlay:
    """Same axes, layered. Built by * operator."""

    def __init__(self, children: Sequence[Node], *,
                 options: "OverlayOptions | None" = None,
                 backend_hint: str | None = None):
        self.children = tuple(children)
        self.options = options or OverlayOptions()
        self.backend_hint = backend_hint
        if len(self.children) == 0:
            raise ValueError("Overlay requires at least one child")
        self._freeze()
    # _freeze / __setattr__ / with_ / __eq__ / __hash__ / __repr__ ...

class Layout:
    """Side-by-side, grid, splitter, tabs, or dock. Built by + operator
    or .grid()/.tabs()/.dock()/.splitter() constructors."""

    def __init__(self, children: Sequence[Node], *,
                 kind: Literal["grid", "splitter", "tabs", "dock"] = "grid",
                 options: "LayoutOptions | None" = None,
                 backend_hint: str | None = None):
        self.children = tuple(children)
        self.kind = kind
        self.options = options or LayoutOptions()
        self.backend_hint = backend_hint
        self._freeze()
```

Where `Node = Element | Overlay | Layout`.

#### Operator semantics

| Form                    | Builds                                |
|-------------------------|----------------------------------------|
| `a * b`                 | `Overlay((a, b))`                      |
| `a + b`                 | `Layout((a, b), kind="grid")`          |
| `a.over(b)`             | sugar for `a * b`                      |
| `Layout.tabs([a, b])`   | tabbed layout                          |
| `Layout.splitter([a,b])`| QSplitter, draggable                   |
| `Layout.dock(center=a, right=b)` | QDockWidget arrangement       |

`Layout.tabs/splitter/dock` are Qt-only — HoloViews doesn't model
them; that's the point of being Qt-native.

#### OverlayOptions

Per Q6 (resolved): an explicit container for shared-axes/title/legend
concerns:

```python
class OverlayOptions:
    def __init__(self, *, title: str | None = None,
                 x_label: str | None = None, y_label: str | None = None,
                 legend: bool = True,
                 background: Color | None = None):
        ...   # _freeze pattern
```

When set on `Overlay`, these win over any child's per-element label.
For per-trace styling (color, alpha, etc.), the child Element wins.

#### LayoutOptions

The `Layout` counterpart — referenced throughout (`§4.1` reads
`LayoutOptions.link_x` to link axes, a Phase 1 acceptance milestone) so it
must be concrete:

```python
class LayoutOptions:
    def __init__(self, *,
                 # grid arrangement (kind="grid")
                 rows: int | None = None,        # None → auto (ceil(sqrt(n)))
                 cols: int | None = None,
                 spacing: int = 6,
                 # axis linking across panes
                 link_x: bool = False,
                 link_y: bool = False,
                 # per-kind metadata
                 tab_labels: Sequence[str] | None = None,        # kind="tabs"
                 dock_areas: Mapping[int, str] | None = None,    # kind="dock"
                 title: str | None = None):
        ...   # _freeze pattern
```

`link_x` / `link_y` drive `ViewBox.setXLink` (pyqtgraph) / `sharex`
(matplotlib) when a single backend hosts the grid; across mixed-backend
panes, axis linking is not available (§2.3, §3.7) and the flags warn-and
-ignore. `tab_labels` and `dock_areas` are consumed by the generic
Qt-level host (§3.7); for `kind="grid"`/`"splitter"` they are ignored.

#### Mixed-backend rule

- **Overlay**: all children must resolve to the same backend. An
  `Overlay` whose negotiation produces different backends per child
  raises `IncompatibleOverlayError`.
- **Layout** (any kind): children may use different backends. Each
  child renders into its own widget; the Layout widget hosts them.

This is the smallest rule that keeps Overlay coherent (single
rendering surface) and Layout maximally flexible. Cross-backend
Overlay is explicitly out of 0.1 scope (§12).

### 2.4 Backend Protocol

```python
class Backend(Protocol):
    """Owns a rendering surface and translates Elements into native
    primitives. Backends are stateless w.r.t. the user — all per-View
    state lives in the RenderHandle the backend returns."""

    name: str                          # "pyqtgraph", "matplotlib", "webengine"
    capabilities: Capabilities         # see 2.5
    renderers: RendererRegistry        # see 2.6

    def supports(self, element_type: type) -> bool:
        """Does this backend have a renderer for this Element type?"""

    def render(
        self,
        node: Node,
        *,
        theme: Theme,
        parent: QWidget | None = None,
    ) -> RenderHandle:
        """Build a fresh widget tree from a Composition root.
        Returns a handle that owns the widget and exposes update/dispose/events.
        **GUI thread only.** See §2.14."""

    def can_host(self, kind: Literal["overlay","grid","splitter","tabs","dock"]) -> bool:
        """Does this backend host this composition kind itself?
        If False, the View wraps the children in a Qt-level container."""
```

Notes:

- `render()` always builds from scratch. Updates go through
  `RenderHandle.update()`, not back through the backend.
- The backend has no global mutable state; each call returns a fresh
  handle. Multiple Views can use the same backend instance.
- `can_host` lets a backend declare e.g. that the matplotlib backend
  hosts "overlay" and "grid" but defers "splitter"/"tabs"/"dock" to a
  generic Qt-level wrapper (since these are pure Qt containers).

### 2.5 Capabilities

Capabilities is `@dataclass(frozen=True)` — it's a backend's static
declaration with no behavior, never subclassed by users. The "plain
class" arguments don't apply.

```python
@dataclass(frozen=True)
class Capabilities:
    dimensions: frozenset[int]          # {2}, {2, 3}
    opengl: bool                        # GPU-accelerated rendering
    picking: Literal["native", "approximate", "none"]
    brush: Literal["native", "approximate", "none"]
    range_events: bool                  # emits range-changed
    streaming: bool                     # incremental append performant
    max_recommended_points: int         # heuristic for auto-routing
    animation: bool
    exports: frozenset[str]             # {"png", "svg", "pdf"}
    threading_model: Literal["gui_only", "render_off_thread"] = "gui_only"
```

Each backend declares its capabilities at import time. The negotiator
uses them to:

- Reject impossible requests early (`Scatter3D` on a 2D-only backend).
- Auto-route at scale: `Scatter(table, scale="auto")` switches the
  pyqtgraph backend onto its Datashader path — a *within-backend* strategy,
  not a separate registered backend (§3.3, §5.1) — when
  `len(table) > backend.capabilities.max_recommended_points`.
- Power the "What backend should I use?" doc page.

### 2.6 RendererRegistry

```python
class RendererRegistry:
    """A backend's mapping from Element type → renderer function.
    Used as: backend.renderers.get(Scatter)(element, ctx) -> primitive."""

    def register(self, element_type: type, fn: ElementRenderer) -> None: ...
    def get(self, element_type: type) -> ElementRenderer | None: ...
    def types(self) -> set[type]: ...
```

Each backend's `__init__.py` builds its registry once:

```python
# qtviz/backends/pyqtgraph/__init__.py
_registry = RendererRegistry()
_registry.register(Scatter, scatter.render)
_registry.register(Curve,   curve.render)
# ...
```

Adding support for a new Element on a backend = one line in the
registry + one new render function. No changes anywhere else.

### 2.7 ElementRenderer signature

```python
ElementRenderer = Callable[[Element, RenderContext], BackendPrimitive]
```

```python
@dataclass
class RenderContext:
    theme: Theme
    parent: QWidget                       # the surface to attach to
    event_bus: EventBus                   # publishes typed events
    backend: Backend                      # back-reference (rare; mostly logging)
    parent_axes: ViewBox | Axes | None    # for overlay children
```

The renderer's job: take the Element, produce the native primitive
(e.g., a `pg.ScatterPlotItem`), attach it to `parent_axes`, wire up
native events to `event_bus`. It returns the primitive so the
RenderHandle can call back into it later.

### 2.8 RenderHandle

```python
class RenderHandle:
    """Owns the rendered widget tree. The bridge from the immutable
    Element world to the mutable Qt world."""

    widget: QWidget
    event_bus: EventBus
    backend_name: str

    def update(self, new_root: Node) -> None:
        """Re-apply the Element tree.
        Phase 1: full rebuild of inner primitives, reusing widget.
        Phase 4+: diffed updates (deferred per Q4 resolved)."""

    def dispose(self) -> None:
        """Release primitives, disconnect events, schedule widget deletion."""

    def export(self, fmt: str, path: Path) -> Path:
        """If the backend declares this export in capabilities."""
```

This is what `View` holds onto. Backend-switching at View level
disposes the old handle and asks a different backend to build a new
one.

#### Composite handles (mixed-backend Layout)

A `Layout` whose children resolve to different backends (§2.3) can't be one
backend's widget tree, so the single-`widget`/single-`event_bus` shape
above doesn't cover it. Such a Layout renders as a
**`CompositeRenderHandle`**:

- `widget` is the Qt container (`QSplitter` / `QTabWidget` /
  `QMainWindow`-with-docks / a `QGridLayout` host) built by the generic
  Qt-level host (§3.7), not by any single backend.
- it owns one child `RenderHandle` per pane (each from that pane's backend)
  and fans `update` / `dispose` / `export` out to them.
- `event_bus` is a *merged* bus: each child bus re-publishes onto it, so
  `View.on(...)` sees one event stream regardless of how many panes or
  backends sit underneath. `source_id` on each `Event` (§2.10)
  disambiguates the origin.

`View` therefore always holds exactly one *root* handle, which is either a
backend's own handle (a single-backend tree — including a single-backend
Layout the backend hosts itself) or a `CompositeRenderHandle`.

### 2.9 View

```python
class View(QWidget):
    """User-facing widget. Owns: an Element tree, a backend choice,
    a theme. Manages the handle lifecycle."""

    def __init__(
        self,
        root: Node,
        *,
        backend: str | Backend = "auto",
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ): ...

    def set_backend(self, name_or_backend: str | Backend) -> None:
        """Dispose current handle, render through new backend.
        Theme + root + event subscriptions preserved."""

    def set_theme(self, theme: Theme) -> None: ...

    def set_root(self, root: Node) -> None:
        """Replace the Element tree; handle.update() called if backend
        unchanged (in Phase 1 always = full rebuild of primitives)."""

    def on(self, event_type: type[Event], cb: Callable[[Event], None],
           *, throttle_ms: int | None = None) -> Disposable:
        """Subscribe to typed events. throttle_ms overrides the default
        for this event type (§2.10)."""

    @property
    def handle(self) -> RenderHandle: ...
```

`View` is a `QWidget` so it drops into any Qt layout. It is the only
class users routinely instantiate.

### 2.10 Event protocol

Backend-agnostic typed events. Events are frozen dataclasses — they're
short-lived data carriers, never subclassed by users.

```python
@dataclass(frozen=True)
class Event:
    source_id: ElementId

@dataclass(frozen=True)
class RangeEvent(Event):
    x: tuple[float, float]
    y: tuple[float, float]

@dataclass(frozen=True)
class PickEvent(Event):
    point_index: int
    x: float
    y: float

@dataclass(frozen=True)
class SelectEvent(Event):
    indices: list[int]
    bounds: tuple[float, float, float, float]   # xmin,ymin,xmax,ymax

@dataclass(frozen=True)
class HoverEvent(Event):
    point_index: int | None     # None = hovered off
    x: float
    y: float

@dataclass(frozen=True)
class TapEvent(Event):
    x: float
    y: float
```

The Phase 1 vocabulary. Backends emit only what their `Capabilities`
declare; capabilities-not-declared = events-never-fired.

**Source identity (Q-D8, applied M4).** `source_id` is *surface-level* for
axes events (`RangeEvent`, `TapEvent`) — minted per rendering surface —
and *element-level* for point events (`PickEvent`, `HoverEvent`) — the
Element's `id`. `SelectEvent` is element-level *with bounds*: a brush emits
one `SelectEvent` per selectable element, carrying that element's `id`, the
in-bounds row `indices`, and the `bounds` (so surface-level subscribers can
react too). This is what lets linked brushing route by element while a
viewport zoom routes by surface.

#### EventBus + throttling

Per Q7 (resolved): subscriptions are throttled by default, with per-event
defaults tuned for Qt's repaint cadence, and overridable per
subscription.

```python
class EventBus:
    DEFAULT_THROTTLE_MS = {
        RangeEvent:  50,    # ~20 Hz; matches Qt repaint comfort zone
        HoverEvent:  33,    # ~30 Hz
        SelectEvent: 50,    # brush-in-progress
        PickEvent:    0,    # discrete click; no throttle
        TapEvent:     0,
    }

    def emit(self, ev: Event) -> None: ...

    def subscribe(
        self,
        event_type: type[Event],
        cb: Callable[[Event], None],
        *,
        throttle_ms: int | None = None,
    ) -> Disposable:
        """throttle_ms = None → use DEFAULT_THROTTLE_MS for event_type.
                       0 → no throttling (every emit delivered).
                       N → trailing-edge throttle: emit immediately,
                           then at most once per N ms with latest payload."""
```

Throttle implementation is the same trailing-edge `QTimer` pattern already
in the webengine code — today the module-level `_Throttle` in
`qtwebplot/core/web_bridge_view.py` (not nested under `WebBridgeView`) —
promoted to `qtviz.core.event` so all backends share one implementation.

`View.on(event_type, cb, throttle_ms=...)` records the subscription in the
View's own canonical registry *and* forwards it to the current
`handle.event_bus.subscribe`. The `Disposable` it returns targets the
View's registry, not a specific bus — so it stays valid across
`set_backend` (§3.5): on a backend switch the View re-binds every live
subscription onto the new handle's (or composite handle's) bus, and
disposing later still works. Disposing a handle directly also tears down
its own bus-level subscriptions as a safety net.

### 2.11 Color

Per Q1 (resolved): simple but flexible. Three accepted forms; a small
`Color` container as the canonical type, with implicit conversion from
strings and tuples.

```python
ColorSpec = Union[
    str,                # known name ("red", "blue", …) or hex ("#rrggbb", "#rrggbbaa")
    tuple[float, float, float],          # (r, g, b) in [0,1]
    tuple[float, float, float, float],   # (r, g, b, a) in [0,1]
    "Color",            # canonical
]
```

`ColorSpec` is **purely visual**. Column-based mapping is never done
through `color=`. Elements that support data-driven color expose a
separate `color_by=` keyword (a column name). Same pattern for size /
size_by and any other visual property that admits data mapping. This
keeps the API context-free: `color=` always means a color value.

The `Color` class:

```python
class Color:
    """Canonical color. Construct from any ColorSpec. Immutable.
    str / tuple inputs auto-convert. Provides backend translations."""

    KNOWN: dict[str, "Color"] = {
        "red":    ...,
        "blue":   ...,
        "green":  ...,
        # … standard set; same names HTML/CSS uses
    }

    def __init__(self, spec: ColorSpec):
        # parse spec into (r, g, b, a) floats in [0, 1]
        ...

    @property
    def rgba(self) -> tuple[float, float, float, float]: ...

    def hex(self) -> str: ...
    def qt(self) -> "QColor": ...        # Qt
    def mpl(self) -> tuple: ...          # matplotlib
    def css(self) -> str: ...            # webengine
```

No column / color ambiguity exists at the type level. `Color("red")`
is a color; `Scatter(color_by="category")` is a column mapping; the
two cannot be confused.

### 2.12 Palette

Per Q2 (resolved): thin wrappers around matplotlib colormaps and Qt
palettes; users can easily build their own.

```python
class Palette:
    """Ordered list of Colors, with optional name and interpolation
    semantics for continuous mappings."""

    def __init__(self, colors: Sequence[ColorSpec], *, name: str | None = None,
                 kind: Literal["discrete", "continuous"] = "discrete"):
        self.colors = tuple(Color(c) for c in colors)
        self.name = name
        self.kind = kind
        self._freeze()

    def at(self, t: float) -> Color:
        """t in [0,1]. Discrete: bucketize. Continuous: interpolate."""

    def __getitem__(self, i: int) -> Color: ...

    @classmethod
    def from_matplotlib(cls, name: str, *, n: int = 10) -> "Palette":
        """Wrap an mpl colormap as a sampled Palette."""

    @classmethod
    def from_qt(cls, palette: "QPalette") -> "Palette":
        """Extract Qt palette colors as a Palette."""

    @classmethod
    def from_hex(cls, hexes: Sequence[str], *, name: str | None = None) -> "Palette":
        """Most common path for users defining a brand palette."""
```

A small registry holds built-ins. Built-ins are **vendored as hex stops**,
not built via `from_matplotlib` — `matplotlib` is an optional extra (§3.6)
and the core registry must populate at import *without* it:

```python
qtviz.palettes.register("viridis", Palette.from_hex(_VIRIDIS_STOPS, kind="continuous"))
qtviz.palettes.register("company", Palette.from_hex(["#1f2937", "#ec4899", "#10b981"]))
qtviz.palettes.get("viridis")        # lookup
qtviz.palettes.list()                # discovery
```

`from_matplotlib` / `from_qt` stay available for *users* who have those
libraries installed; the core simply doesn't depend on them. The user adds
one palette with one call.

### 2.13 Theme

A `Theme` exists today (`qtwebplot.theme.Theme`) but as a carrier of **hex
strings**: `background`/`foreground`/`grid: str` and
`palette: tuple[str, ...]`, with no font sizes. The renderer sketches in
this spec call `ctx.theme.foreground.qt()` and expect `theme.palette` to be
a `Palette` (§2.12). Reconciling the two is a **real migration, not the
"minor cleanup" the earlier §13 note implied**:

- `background` / `foreground` / `grid` become `Color` (§2.11), accepting
  str/tuple inputs and normalizing in `__init__`, so every backend can do
  `theme.foreground.qt()` / `.mpl()` / `.css()` uniformly.
- `palette` becomes a `Palette` (§2.12).
- add `font_family: str` plus `font_size` / `title_size` (the "+ sizes").
- keep `Theme.light()` / `dark()` / `from_qt_palette()` / `from_qt_app()`;
  they now build `Color`/`Palette` instead of strings.

This is a breaking change to the current `Theme`. It is small and confined
(one module + the webengine backend's `apply_theme`) but must be done
deliberately in Phase 1, not hand-waved. Each backend keeps an
`apply_theme(widget, theme)` that walks its widget tree.

Theme is applied at render time and on `set_theme` on the View. Theme is
**not** part of `Element` — Elements are theme-agnostic. Theme lives in
`RenderContext`.

### 2.14 Threading model

Per Q5 (resolved): we set up the foundations now so future work
(streaming sources, background queries, animations, lazy DataSources)
doesn't fight the framework.

#### Core rules

1. **All Qt object construction & mutation happens on the GUI thread.**
   This is Qt's hard requirement, not negotiable.
2. **All renderer code is GUI-thread-only.** Renderers create / mutate
   widgets and primitives.
3. **Data prep, queries, file I/O, expensive transforms run on worker
   threads.** Workers deliver results to the GUI thread via Qt signals
   or `qtviz.threading.run_on_gui()`.
4. **`Signal.set(value)` is thread-safe.** A `Signal` set from a worker
   schedules its dependent re-render on the GUI thread automatically
   (queued connection).
5. **Events fire on the GUI thread.** Subscribers can safely touch
   widgets without further marshaling.

#### Mechanisms provided

A small `qtviz.threading` module:

```python
def gui_thread() -> QThread:
    """Return the GUI (main) thread."""

def is_gui_thread() -> bool: ...

def require_gui_thread(fn):
    """Decorator. Raises RuntimeError if called off the GUI thread.
    Applied to: Backend.render, RenderHandle.update/dispose,
    View.set_backend/set_theme/set_root, every ElementRenderer."""

def run_on_gui(fn: Callable[[], T], *, block: bool = False) -> Future[T]:
    """Schedule fn on the GUI thread via QMetaObject.invokeMethod
    with a queued connection. If block=True, wait for completion.
    Called from the GUI thread itself: short-circuits and just calls
    fn() directly (no deadlock; permissive for utility callers)."""

class Worker(QObject):
    """Public convenience class — exposed at `qtviz.threading.Worker`
    for DataSource implementers, plugin authors, and Studio users.
    A QObject that lives on a QThread, runs callables submitted via
    `.submit(fn) → Future[T]`, and emits results on the GUI thread
    via Qt signal."""
```

#### Backend-specific notes

| Backend     | Threading caveats                                                              |
|-------------|--------------------------------------------------------------------------------|
| pyqtgraph   | All `ScatterPlotItem` / `PlotItem` / `ImageItem` ops on GUI thread. `useOpenGL=True` is even stricter — OpenGL context belongs to the GUI thread. |
| matplotlib  | All `Figure` / `Axes` ops on GUI thread. `FigureCanvasQTAgg` redraws via Qt event loop. |
| webengine   | All `QWebEnginePage` / `runJavaScript` calls on GUI thread. Messages from JS via `QWebChannel` arrive on the GUI thread automatically. |

All three are GUI-thread-only for renderer code. Backends advertise
this via `Capabilities.threading_model = "gui_only"`. The
`threading_model` field exists to allow a future backend (e.g., a
GPU compute backend that does its work off-thread) to declare
otherwise — the architecture supports it, no current backend uses it.

#### What gets enforced today

- `@require_gui_thread` on every renderer, `RenderHandle.update`,
  `Backend.render`, `View.set_backend / set_theme / set_root`.
- `DataRef.materialize()` on a lazy ref (dask/zarr/`DataSource`): runs the
  narrowed compute/I/O on a worker; the View handles the resulting eager
  ref and re-renders when ready (the materialize pass, §6.2). Cheap
  metadata ops (`schema`/`size`/`extent`/`select`/`window`) stay on the GUI
  thread — they build graphs / read attrs, they don't compute.
- `Signal.set()` from any thread: implemented via a `QObject` that
  emits a Qt signal connected `Qt.QueuedConnection` to the dependent
  renderer's update slot.
- A pre-commit hook / test asserting no renderer mutates Qt objects
  outside `require_gui_thread`-guarded code paths.

#### What is deferred

- Off-thread rendering (a backend that produces a pixmap on a worker
  and blits it on the GUI thread). The `threading_model` capability
  is there; the implementation isn't built. Animation in Phase 6+
  may need this.

## 3. Backend selection & switching

### 3.1 Levels of choice (most specific wins)

1. **Element-level hint**: `Scatter(table, x="a", y="b", backend_hint="pyqtgraph")`.
2. **Composition-level hint**: `Overlay(..., backend_hint="matplotlib")`
   — applies to children whose `backend_hint` is `None`.
3. **View-level**: `View(root, backend="pyqtgraph")`.
4. **Global default**: `qtviz.set_default_backend("pyqtgraph")` — fallback.

Precedence: Element > Composition > View > Global. The negotiator
resolves these into a concrete `Backend` per node.

### 3.2 Negotiation algorithm

```python
def negotiate(node: Node, view_backend: str, *, ancestor_hint=None):
    chosen = node.backend_hint or ancestor_hint or view_backend or global_default()
    if chosen == "auto":
        return auto_negotiate(node, ancestor_hint=ancestor_hint)   # §3.3
    if isinstance(node, Overlay):
        for child in node.children:
            child_chosen = negotiate(child, view_backend, ancestor_hint=chosen)
            if child_chosen != chosen:
                raise IncompatibleOverlayError(...)
        return chosen
    if isinstance(node, Layout):
        for child in node.children:
            negotiate(child, view_backend, ancestor_hint=chosen)
        return chosen
    # Element
    if not backend_registry[chosen].supports(type(node)):
        raise UnsupportedElementError(
            f"{type(node).__name__} not supported on {chosen}; "
            f"supported on: {supported_backends(type(node))}"
        )
    return chosen
```

The `chosen == "auto"` branch matters: `view_backend` defaults to `"auto"`
(§2.9), which is a *truthy string* and would otherwise be looked up as a
backend name and fail. Auto resolution hands off to §3.3.

Deterministic; runs once per `set_root`, and may be memoized on the root's
value-hash (§2.1, now well-defined) so re-applying an equal tree skips
re-negotiation. Errors are loud and actionable. Lives in
`qtviz.core.compose` per Q9 (resolved).

### 3.3 Auto mode

`backend="auto"` resolves each node to a concrete backend by capability +
size. It never returns a pseudo-backend: **Datashader is not a backend** —
it is a scale strategy *inside* the pyqtgraph backend, selected by
`Scatter(scale=...)` (§5.1, §2.5, roadmap Phase 4). Auto only ever picks
from the registered backends.

```python
def auto_negotiate(node, *, ancestor_hint=None):
    if isinstance(node, Overlay):
        # Overlay is single-surface: resolve ONE backend for all children
        # (Overlay coherence, §2.3). Collapse, don't raise.
        picks = {auto_element_backend(c) for c in elements_of(node)}
        return highest_priority(picks)
    if isinstance(node, Layout):
        for child in node.children:        # panes may each differ
            auto_negotiate(child)
        return "auto"                      # the host (§3.7) arranges per pane
    return auto_element_backend(node)      # Element

def auto_element_backend(el):
    candidates = [b for b in registered if b.supports(type(el))]
    if not candidates:
        raise NoBackendFor(el)
    n = data_size(el)
    if n is not None and n > 1_000_000:
        return max(candidates, key=lambda b: b.capabilities.max_recommended_points)
    return max(candidates, key=lambda b: -priority_index(b.name))
```

`data_size(el)` is cheap by construction — for in-memory refs it's
`len` / `.shape[0]`; for a lazy `DataSource` (Phase 5) it's the source's
known/estimated row count, **never a forced full snapshot** (auto must not
trigger I/O). It returns `None` when size is unknown, and auto then routes
by priority.

Priority order (default, per Q10): `pyqtgraph` > `matplotlib` >
`webengine`. Tunable via `qtviz.set_backend_priority([...])`.

Auto is a **convenience** layer — never silent magic. Whatever it picks is
logged at INFO and visible on the handle (`handle.backend_name`). When an
Overlay's children would auto-pick *different* backends, auto collapses
them to the single highest-priority common backend (and logs it) rather
than raising `IncompatibleOverlayError` — that error is reserved for
*explicit* conflicting hints (§3.2), where the user asked for something
impossible.

### 3.4 Option compatibility & graceful degradation

Every Element option falls in one of three classes (declared via
class attributes on the Element subclass, per §2.1):

1. **Required by the contract** — every backend must support it. Listed
   in `Element.REQUIRED_OPTIONS`. E.g., `Scatter.x`, `Scatter.y`. If a
   backend can't honor a required option, it can't claim to support the
   Element.
2. **Recommended** — most backends support it; missing → one-time
   warning logged with backend + option name; rendering proceeds.
   Listed in `Element.RECOMMENDED_OPTIONS`. E.g., `Scatter.alpha`,
   `Scatter.marker`.
3. **Backend-specific** — namespaced fields (`pyqtgraph_use_opengl`,
   `matplotlib_rasterized`). Other backends ignore silently. Convention:
   `<backend_name>_<option>`. The negotiator extracts these and only
   exposes the relevant ones to each backend's renderer.

Each backend's renderer logs unsupported recommended options once,
then silences. This is the contract that lets backends differ in
detail without breaking the abstraction. **Most flexibility lives in
classes 2 and 3.**

### 3.5 Runtime switching

```python
view = View(root, backend="pyqtgraph")
view.show()
view.set_backend("matplotlib")
```

Implementation: `set_backend` is `@require_gui_thread`. Calls
`handle.dispose()`, negotiates against the new backend, asks the new
backend to render the same root, swaps `view`'s child widget. Theme
and root are preserved. Event subscriptions transfer: `View` retains
the subscription list and re-registers each with the new bus.

If the new backend doesn't support all Elements in the tree, raise
before disposing the old handle (atomic switch).

### 3.6 Backend availability & defaults

Per Q8 (resolved):

- **`pyqtgraph` is a hard dependency.** Always importable; always
  registered. The first-choice default. Reasoning: pyqtgraph is the
  primary differentiator (native, fast, interactive); a user installing
  qtviz expects it to Just Work.
- **`matplotlib` is an optional extra**: `pip install qtviz[matplotlib]`.
  Lazy import — registered if importable.
- **`webengine` is an optional extra**: `pip install qtviz[webengine]`.
  Lazy import — registered if importable. (PySide6 itself is a hard
  dep; QtWebEngine often ships separately and is heavyweight.)
- **Auto-detect at import time**: `qtviz.__init__` attempts to register
  each optional backend in a try/except; missing imports are logged
  once at INFO on first qtviz import (one line per missing optional
  backend, with the install hint inline).
- **`qtviz.backends.list_available()`** returns the registered set.
- Requesting an unavailable backend raises with a clear install hint:
  `"backend 'matplotlib' not available; pip install qtviz[matplotlib]"`.

### 3.7 Generic Qt-level layout host

`Layout(kind="splitter" | "tabs" | "dock")`, and any `Layout(kind="grid")`
whose children resolve to more than one backend, are hosted by a
backend-neutral component — `qtviz.core._host.LayoutHost` (kept out of
`compose.py` so negotiation stays Qt-free) via the `render_root` entry — *not* by a
backend's `render()`. For each child it runs negotiation (§3.2), asks the
chosen backend to render that child into its own widget, and arranges the
resulting widgets in a `QSplitter` / `QTabWidget` /
`QMainWindow`-with-docks / `QGridLayout`. It returns a
`CompositeRenderHandle` (§2.8).

A backend's `can_host(kind)` (§2.4) returns True only for kinds it arranges
*internally with shared primitives* — e.g. pyqtgraph hosts `grid` via
`GraphicsLayoutWidget` (and gets cheap linked axes) *when every child is
pyqtgraph*. When `can_host` is False, or the children span backends, the
`LayoutHost` takes over and per-pane axis linking is unavailable. `Overlay`
is never host-delegated: it is single-surface by definition and
single-backend by rule (§2.3).

This is the piece that makes "Layout children may use different backends"
(§2.3) actually buildable; without a named owner it was implied but
homeless.

## 4. Backend implementations — Phase 1

The per-backend directory trees below (one renderer module per Element
under `elements/`) supersede the flatter sketch in `roadmap.md §2`
(`renderer.py` + sibling `scatter.py` files) — follow this spec where they
differ. Note the two distinct `scatter.py` roles: the Element *type* lives
in `qtviz/elements/scatter.py`; each backend's *renderer* for it lives in
`qtviz/backends/<backend>/elements/scatter.py`.

### 4.1 pyqtgraph backend (hard dep, primary)

```
qtviz/backends/pyqtgraph/
├── __init__.py              # Backend instance, registry, capabilities
├── render.py                # render() and RenderHandle subclass
├── _axes.py                 # ViewBox helpers, axis linking
├── _events.py               # native → typed event translators
├── _theme.py                # apply_theme on GraphicsLayoutWidget
└── elements/
    ├── scatter.py
    ├── curve.py
    ├── bars.py
    ├── image.py
    ├── heatmap.py
    ├── histogram.py
    ├── errorbars.py
    └── spread.py
```

**Capabilities**:

```python
Capabilities(
    dimensions=frozenset({2}),
    opengl=True,
    picking="native",                    # ScatterPlotItem.sigClicked
    brush="native",                      # LinearRegionItem / PolyLineROI
    range_events=True,                   # ViewBox.sigRangeChanged
    streaming=True,                      # setData efficient for moderate sizes
    max_recommended_points=2_000_000,    # native; >1M auto-routes to datashader
    animation=False,
    exports=frozenset({"png", "svg"}),
    threading_model="gui_only",
)
```

**Top-level render**:

- `Overlay`: one `pg.PlotItem` inside a `GraphicsLayoutWidget`; each
  child renders into the same `ViewBox`.
- `Layout(grid)`: `GraphicsLayoutWidget.addPlot(row, col)` per child.
  Linked axes via `viewBox.setXLink(other)` when `LayoutOptions.link_x`.
- `Layout(splitter/tabs/dock)`: `can_host("splitter")` returns False;
  the View wraps the children in a `QSplitter` / `QTabWidget` /
  `QMainWindow`-with-docks, each pane containing a fresh pyqtgraph
  render.

**Per-element render functions** are 30–60 LOC each:

```python
# qtviz/backends/pyqtgraph/elements/scatter.py
def render(element: Scatter, ctx: RenderContext):
    data = element.data                  # already eager + narrowed (§6.2)
    item = pg.ScatterPlotItem(
        x=data.series(element.x),        # TabularRef.series → 1-D numpy
        y=data.series(element.y),
        pen=ctx.theme.foreground.qt(),
        brush=_resolve_color(element.color, ctx.theme).qt(),
        size=element.size or 6,
        useCache=True,
    )
    if element.pyqtgraph_use_opengl:
        item.setOpts(useOpenGL=True)
    ctx.parent_axes.addItem(item)
    _events.wire_scatter(item, element.id, ctx.event_bus)
    return item
```

### 4.2 matplotlib backend (optional extra)

```
qtviz/backends/matplotlib/
├── __init__.py
├── render.py                # FigureCanvasQTAgg wrapper
├── _events.py               # mpl event → typed event
├── _theme.py                # rcParams from Theme
└── elements/
    ├── scatter.py
    ├── curve.py
    └── ...
```

**Capabilities**:

```python
Capabilities(
    dimensions=frozenset({2, 3}),        # mpl_toolkits.mplot3d
    opengl=False,
    picking="native",
    brush="approximate",                 # RectangleSelector — slower than pg
    range_events=True,                   # 'xlim_changed' callback
    streaming=False,                     # no efficient incremental path
    max_recommended_points=100_000,
    animation=True,
    exports=frozenset({"png", "svg", "pdf"}),
    threading_model="gui_only",
)
```

- `Overlay`: one `Figure`, one `Axes`; all children draw into it.
- `Layout(grid)`: `Figure.subplots(rows, cols)`; linked axes via
  `sharex=...` if `link_x`.
- `Layout(splitter/tabs/dock)`: same as pyqtgraph — defer to View.

The biggest engineering item is the event bridge: mpl events fire in
mpl's own event loop. They marshal into the qtviz EventBus via
`qtviz.threading.run_on_gui()` since the EventBus + subscribers
expect GUI-thread delivery (matplotlib events already fire on the
GUI thread when using the Qt5Agg backend, but the marshaling guards
against future backend changes and keeps the contract clean).

### 4.3 webengine backend (optional extra; rehome)

```
qtviz/backends/webengine/
├── __init__.py
├── render.py
├── view.py                  # current WebBridgeView (carryover)
├── bridge.py                # current Bridge (carryover)
├── _runtime.py / _inject.py # carryover
├── _events.py
├── _theme.py
└── elements/
    ├── scatter.py           # routes through Plotly or Bokeh JS
    └── ...                  # one per Element type we expose
```

**Capabilities**:

```python
Capabilities(
    dimensions=frozenset({2, 3}),
    opengl=True,                         # via Plotly's WebGL traces
    picking="native",
    brush="native",
    range_events=True,
    streaming=True,                      # extendTraces / patch / stream
    max_recommended_points=500_000,
    animation=True,
    exports=frozenset({"png", "html"}),
    threading_model="gui_only",
)
```

The current `PlotlyBackend` / `BokehBackend` / `HoloViewsBackend`
classes are repurposed as **JS-routing strategies** inside the
webengine backend's element renderers. The user-facing Element API
doesn't expose this; it picks the right JS library per Element type
internally. Rehoming detail in Phase 5; this section is a sketch.

## 5. Element specs (Phase 1 vocabulary)

For each: required fields, recommended options, backend-specific
options, backend support matrix. Each uses the plain-class pattern
from §2.1.

### 5.1 Scatter

Visual properties that admit data mapping have a paired `_by` keyword.
`color` and `color_by` are mutually exclusive (raise if both); same
for `size` / `size_by`. This applies the §2.11 / Q-A clean-API rule.

```python
class Scatter(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "color_by", "size", "size_by", "alpha", "marker")

    def __init__(self, data, *, x: str, y: str,
                 color: ColorSpec | None = None,    # static visual color
                 color_by: str | None = None,        # column to color-map
                 size: float | None = None,          # static numeric size
                 size_by: str | None = None,         # column to size-map
                 marker: Literal["circle","square","triangle","diamond","cross"] = "circle",
                 alpha: float = 1.0,
                 scale: Literal["native", "auto", "datashader"] = "native",
                 backend_hint: str | None = None, id=None,
                 pyqtgraph_use_opengl: bool = False,
                 matplotlib_rasterized: bool = False):
        super().__init__(backend_hint=backend_hint, id=id)
        if color is not None and color_by is not None:
            raise ValueError("Scatter: pass color (static) or color_by (column), not both")
        if size is not None and size_by is not None:
            raise ValueError("Scatter: pass size (static) or size_by (column), not both")
        self.data, self.x, self.y = data, x, y
        self.scale = scale
        self.color, self.color_by = color, color_by
        self.size, self.size_by = size, size_by
        self.marker, self.alpha = marker, alpha
        self.pyqtgraph_use_opengl = pyqtgraph_use_opengl
        self.matplotlib_rasterized = matplotlib_rasterized
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self._freeze()
```

The `_by` pattern is the convention. Any other Element that grows
a data-driven mapping in the future follows it.

`scale` selects the rendering strategy, not the backend: `"native"` draws
every point (Phase 1, the only value wired then); `"datashader"` forces the
pyqtgraph backend's aggregate-to-`ImageItem` path; `"auto"` picks between
them by point count (§2.5). `"auto"`/`"datashader"` are **honored from
Phase 4** when the Datashader integration lands — until then a non-native
`scale` warns and falls back to `"native"`. `scale` is only meaningful on
backends whose capabilities support it; others ignore it.

Support: pyqtgraph (native), matplotlib (native), webengine (Plotly Scattergl).

### 5.2 Curve

```python
class Curve(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "alpha")

    def __init__(self, data, *, x, y, color=None, line_width=1.5,
                 line_style: Literal["solid","dashed","dotted","dashdot"]="solid",
                 alpha=1.0, backend_hint=None, id=None):
        ...
```

Support: pyqtgraph (PlotCurveItem), matplotlib (Axes.plot), webengine (Plotly Scatter mode="lines").

### 5.3 Bars

```python
class Bars(Element):
    REQUIRED_OPTIONS = ("x", "y")
    RECOMMENDED_OPTIONS = ("group", "color", "orient")

    def __init__(self, data, *, x, y, group=None, orient="v",
                 color=None, backend_hint=None, id=None): ...
```

Support: pyqtgraph (BarGraphItem), matplotlib (Axes.bar), webengine (Plotly Bar).

### 5.4 Image

```python
class Image(Element):
    REQUIRED_OPTIONS = ("bounds",)
    RECOMMENDED_OPTIONS = ("colormap", "interpolation")

    def __init__(self, data: ArrayLike, *,
                 bounds: tuple[float, float, float, float],
                 colormap: str = "viridis",
                 interpolation: Literal["nearest", "bilinear"] = "bilinear",
                 backend_hint=None, id=None): ...
```

Support: pyqtgraph (ImageItem), matplotlib (Axes.imshow), webengine (Plotly Image).

### 5.5 Heatmap

A regular grid addressed by `x`/`y`/`z` columns of a tabular ref (matching
the roadmap's `Heatmap(table, x, y, z)`): rows pivot into a 2-D value grid
keyed by `(x, y)` and colored by `z`. Shape like Image once gridded, but
driven from a table rather than a raw array.

```python
class Heatmap(Element):
    REQUIRED_OPTIONS = ("x", "y", "z")
    RECOMMENDED_OPTIONS = ("colormap", "aggregator")

    def __init__(self, data, *, x: str, y: str, z: str,
                 colormap: str = "viridis",
                 aggregator: Literal["mean","sum","count","max","min"] = "mean",
                 backend_hint=None, id=None): ...
```

`aggregator` resolves duplicate `(x, y)` pairs into one cell. Support:
pyqtgraph (`ImageItem` over the pivoted grid), matplotlib (`pcolormesh`),
webengine (Plotly Heatmap).

### 5.6 Histogram

```python
class Histogram(Element):
    REQUIRED_OPTIONS = ("column",)
    RECOMMENDED_OPTIONS = ("bins", "density", "color")

    def __init__(self, data, *, column, bins: int | str = "auto",
                 density: bool = False, color=None,
                 backend_hint=None, id=None): ...
```

Support: all three.

### 5.7 ErrorBars

```python
class ErrorBars(Element):
    REQUIRED_OPTIONS = ("x", "y", "err")
    RECOMMENDED_OPTIONS = ("direction", "color")

    def __init__(self, data, *, x, y,
                 err: str | tuple[str, str],
                 direction: Literal["y", "x", "both"] = "y",
                 color=None, backend_hint=None, id=None): ...
```

Support: pyqtgraph (ErrorBarItem), matplotlib (Axes.errorbar), webengine (Plotly).

### 5.8 Spread

Filled band between two y-series. Common in time-series with
confidence intervals.

```python
class Spread(Element):
    REQUIRED_OPTIONS = ("x", "y_lo", "y_hi")
    RECOMMENDED_OPTIONS = ("color", "alpha")

    def __init__(self, data, *, x, y_lo, y_hi,
                 color=None, alpha: float = 0.3,
                 backend_hint=None, id=None): ...
```

Support: pyqtgraph (FillBetweenItem), matplotlib (Axes.fill_between), webengine (Plotly fill="tonexty").

## 6. Data layer — containers, laziness, adapters

The data layer is a first-class subsystem with the **same plug-in shape as
backends** (§7): a small contract (`DataRef`, §2.1), a set of adapters that
satisfy it, and a registry that loads an adapter only when its container
library is present. Adding a container type = adding an adapter; no core,
renderer, Element, or negotiation file changes. This is the data-side
mirror of the backend abstraction, and it is what lets the library bind to
whatever container a data-intensive user already has — pandas today, an
out-of-core dask/zarr array tomorrow — without an API change.

### 6.1 Two shapes

| Shape | Addressed by | Renderer call | Containers |
|-------|--------------|---------------|------------|
| **Tabular** | column name | `series(name) -> 1-D ndarray` | dict, pandas, polars, Arrow, structured ndarray, dask.DataFrame |
| **Gridded** | dim / coord | `grid(value) -> (2-D values, x, y)` | ndarray, xarray, zarr, dask.array |

An Element's field references (`x`, `y`, `z`, `color_by`, …) are **names**
the ref resolves against whichever shape it is — `x="time"` works whether
`time` is a DataFrame column or an xarray coordinate. Point/line/hist
Elements need a tabular-resolvable ref; Image and Heatmap-from-grid need a
gridded one. A ref may bridge shapes where it's unambiguous (a 1-D xarray
`DataArray` yields its dim as `x`, its values as `y`); where it can't, the
Element raises a clear shape error at construction.

### 6.2 Laziness — narrow before you pull

Out-of-core containers (dask, zarr, a Phase-5 query `DataSource`) must never
be fully materialized just to draw a viewport. The contract (§2.1) splits
into **cheap metadata ops** (sync, GUI-thread-safe — `schema` / `size` /
`extent` / `select` / `window` / `fingerprint`) and **one expensive op**
(`materialize`, Worker-only). The render pipeline always runs:

```
negotiate → select(needed names) → window(viewport) → materialize() → render
            └────────── cheap, pushed down into dask/zarr ──────────┘ └ Worker ┘
```

`select` / `window` push projection and slicing **down** into the container
(dask builds a smaller graph; zarr reads fewer chunks) so `materialize`
computes only the visible, needed slice — then hands renderers an eager ref
whose `series` / `grid` are plain sync numpy. For eager in-memory refs every
step is a cheap no-op and `materialize` returns `self`. Big-data scale
strategies (Datashader, §2.5 / §5.1) instead take `native()` and aggregate
the lazy object directly, never round-tripping a dense ndarray through the
GUI thread. Viewport-driven re-aggregation (pan/zoom → new `window` →
re-`materialize`, debounced) is the Phase 4 mechanism; the seam is here in
Phase 1.

### 6.3 Adapter registry

```python
class DataAdapter(Protocol):
    priority: int
    def handles(self, obj: Any) -> bool: ...
    def wrap(self, obj: Any) -> DataRef: ...

def register_data_adapter(a: DataAdapter) -> None: ...
```

`as_data_ref` tries adapters by descending priority. **Optional adapters
auto-register iff their library imports** — exactly the §3.6 backend
pattern — and live in `qtviz/data/adapters/` or arrive from third parties
via the `qtviz.data_adapters` entry-point group. We ship the *contract +
the eager adapters*; the lazy/gridded adapters land with the reactive/data
phases:

| Adapter | Shape | Lazy | Phase |
|---------|-------|------|-------|
| `dict` / ndarray / pandas / Arrow | tab / grid | no | 1 |
| `Signal` | follows wrapped | reactive | 4 |
| `xarray` (DataArray / Dataset) | gridded | no (in-mem) | when prioritized |
| `dask.array` / `dask.DataFrame` | grid / tab | **yes** | 4–5 |
| `zarr` | gridded | **yes** | 4–5 |
| `DataSource` (DuckDB / Parquet / SQL) | tabular | **yes** | 5 |

Because `is_lazy`, `select`, `window`, `materialize`, and `native` are in
the contract from day one, each later container is *one new adapter file*.
A round-trip conformance suite (dev-plan §5.3, adapter variant) renders the
same Element through every registered adapter and asserts identical output
— the test the data abstraction must pass, mirroring §7 for backends.

### 6.4 Phase 1 scope

- **Eager adapters only**: `dict[str, array]`, numpy (structured → tabular,
  plain → gridded), pandas, Arrow. `materialize` = identity; the
  narrow→materialize seam exists but is a no-op so the lazy adapters slot in
  later without reshaping the pipeline or the View.
- **`Signal[Data]`** (Phase 4): reactive ref. `series` / `grid` read the
  current value; `subscribe(cb)` triggers re-render. Cross-thread
  `Signal.set` per §2.14. **Requires an initial value** (Q-B); `None` only
  when the wrapped type permits it (`Signal[pa.Table | None]`).
- **`fingerprint`**: buffer `id()` in-memory; `dask.base.tokenize` for
  dask; version counter for `Signal` (Q-O).
- **`extent`** is best-effort: cheap from dask/zarr/xarray metadata or attrs
  where available; if computing a true min/max would force I/O, it returns
  `None` and the backend falls back to auto-ranging on the materialized
  slice. (How aggressively to compute extents for initial axes is noted in
  `discussion-items.md` [D1].)

## 7. Adding a new backend (the test of the design)

To prove the backend abstraction is right, walking through a
hypothetical fourth backend (`bokeh-server`):

1. `mkdir qtviz/backends/bokeh_server/`
2. Implement `Backend` Protocol: capabilities, render, can_host.
3. Implement one `ElementRenderer` per Element type supported. Skip
   the rest; `supports()` declares only what's implemented.
4. Register in `qtviz/backends/__init__.py` or via setuptools
   entry-point for third-party plugins:

```toml
# pyproject.toml of a third-party plugin
[project.entry-points."qtviz.backends"]
bokeh_server = "qtviz_bokeh_server:backend"
```

No file in `qtviz/core/`, `qtviz/elements/`, or any other backend is
modified. This is the test the design must pass.

## 8. HoloViews adapter (Phase 3 sketch)

```python
def from_holoviews(obj) -> Node:
    """Translate a HoloViews tree into a qtviz Node."""
    if isinstance(obj, hv.Scatter):
        return Scatter(data=obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.Curve):
        return Curve(data=obj.dframe(), x=obj.kdims[0].name, y=obj.vdims[0].name)
    if isinstance(obj, hv.Overlay):
        return Overlay(tuple(from_holoviews(c) for c in obj))
    if isinstance(obj, hv.Layout):
        return Layout(tuple(from_holoviews(c) for c in obj), kind="grid")
    if isinstance(obj, hv.DynamicMap):
        ...   # signal-driven
    raise UnsupportedHoloViewsElement(type(obj).__name__)
```

`DynamicMap`: subscribe to HoloViews's stream events; translate each
update into a `Signal` value change, which drives a re-render.

Streams (`RangeXY`, `BoundsXY`, `Tap`, `Selection1D`): register our
typed events on the resulting View and forward to the HoloViews
stream's `event()` method, so HoloViews-side callbacks fire normally.

## 9. Reactive layer (Phase 4 sketch)

S-style minimal:

```python
class Signal[T]:
    def get(self) -> T: ...
    def set(self, v: T) -> None: ...
    def subscribe(self, cb: Callable[[T], None]) -> Disposable: ...

def derived[T](f: Callable[[], T]) -> Signal[T]: ...
def effect(f: Callable[[], None]) -> Disposable: ...
```

A View subscribes to all Signals referenced in its Element tree via
the same `subscribe` mechanism `DataRef` uses. Any signal change
schedules a re-render on the next Qt event loop tick (debounced,
trailing-edge — same throttle pattern as Events).

Cross-thread `.set` per §2.14: `Signal` internally holds a `QObject`
and emits a queued signal connection.

Scope is intentionally tiny: no async, no time-travel, no remote-source
plumbing. ~500 LOC.

## 10. Studio (Phases 7+, sketch)

Studio plots through `qtviz.View` only; it never touches a backend
directly. The Studio backend selector toolbar calls
`view.set_backend(name)` and shows a capability matrix tooltip when
hovering names.

Studio dashboards serialize as the Element tree + backend choice +
theme; reopening rebuilds them deterministically.

Detailed Studio spec lands when Phase 6 starts.

## 11. Resolved decisions + remaining open questions

### Resolved (this revision)

| # | Question                                         | Resolution                                                                                          |
|---|--------------------------------------------------|------------------------------------------------------------------------------------------------------|
| 1 | Color type spec                                  | Union(str, tuple, `Color` class); `Color` is canonical, parses any form. Column-mapping via context. §2.11 |
| 2 | Palette definition                               | Thin `Palette` class wrapping mpl colormaps + Qt palettes; `from_hex` for user palettes; small registry. §2.12 |
| 3 | dataclass vs plain Python class                  | Plain Python class for user-extensible types (Element, Options, composition). Frozen dataclasses for internal carriers (Capabilities, Events, RenderContext). §2 preamble + §2.1 |
| 4 | Update-in-place vs rebuild                       | Always rebuild in Phase 1. Diffing deferred to Phase 4+ when measured. §2.8 |
| 5 | Threading model                                  | All Qt mutation on GUI thread; `qtviz.threading` module with `require_gui_thread`, `run_on_gui`, `Worker`. Capabilities declare `threading_model`. §2.14 |
| 6 | Overlay.options vs child options                 | Explicit `OverlayOptions` for title/labels/legend/background (Overlay wins); per-trace styling stays on child Element. §2.3 |
| 7 | Event throttling                                 | Default per-event-type throttle (Range/Hover/Select: 33–50 ms; Pick/Tap: 0); user override via `throttle_ms=` on subscribe. §2.10 |
| 8 | Lazy backend imports + required default          | `pyqtgraph` hard dep, always registered. `matplotlib`/`webengine` lazy via extras. §3.6 |
| 9 | Where do composition rules live?                 | `qtviz.core.compose` owns negotiation + validation; backends never see Element types they don't support. §3.2 |
| 10| Default global backend                           | `pyqtgraph` first, then `matplotlib`, then error. §3.3 |

### Resolved (follow-up questions)

| # | Question                                                                 | Resolution                                                                                          |
|---|--------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| A | Color / column ambiguity in `Scatter(color=...)`                          | Removed at the API level — `color=` is purely visual; `color_by=` takes a column name. Same pattern for `size`/`size_by`. Mutually-exclusive validation in `__init__`. §2.11 and §5.1 |
| B | `Signal[Data]` initial value                                              | Initial value is required at construction. `None` allowed only when the type permits it explicitly. §6 |
| C | Element `id` format                                                       | UUID4-derived string — stable across processes for Studio persistence. §2.1 |
| D | Lazy backend import diagnostics                                            | At runtime, one INFO log per missing optional backend on first import, with the install hint inline. §3.6 |
| E | `run_on_gui(fn, block=True)` called from the GUI thread                   | Short-circuits to direct call (no deadlock; permissive). §2.14 |
| F | Expose `Worker` to users?                                                 | Yes — `qtviz.threading.Worker` is public API for DataSource implementers, plugin authors, Studio users. §2.14 |

### Resolved (spec-review pass)

Decisions taken to close gaps found reviewing the draft. Flagged here so
they read as choices, not silent edits — override any that are wrong.

| # | Question                                                                 | Resolution                                                                                          |
|---|--------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| G | Element `__eq__`/`__hash__` over array/DataFrame data (would raise / misbehave) | Value identity excludes `id` and represents each DataRef by `.fingerprint()` (buffer identity), never raw contents. Arrays are never hashed/compared by value. §2.1 |
| H | Raw `data` has no uniform accessor the renderers assume                   | Element normalizes any input through the `as_data_ref()` adapter registry into a `DataRef` (`TabularRef`/`GriddedRef`); renderers read `series()`/`grid()`, never the raw container. Expanded into the §6 data layer. §2.1, §6 |
| I | `LayoutOptions` referenced (`link_x`, grid shape) but undefined           | Defined: `rows`/`cols`/`spacing`, `link_x`/`link_y`, `tab_labels`, `dock_areas`, `title`. §2.3 |
| J | Single handle/bus model vs mixed-backend Layout                           | Mixed-backend Layout renders as `CompositeRenderHandle` (Qt container widget + merged event bus over per-pane child handles), built by `LayoutHost`. View always holds one root handle. §2.8, §3.7 |
| K | Subscription/`Disposable` lifetime across `set_backend`                   | View owns the canonical subscription registry; Disposables target it, survive backend switches, and the View re-binds them onto the new bus. §2.10, §3.5 |
| L | Theme "already exists" vs renderers calling `theme.foreground.qt()`       | Real migration: Theme fields become `Color`/`Palette` (+ font sizes); breaking but confined. Built-in palettes vendored as hex (no hard matplotlib dep). §2.12, §2.13 |
| M | `negotiate()` breaks for the default `backend="auto"`; auto + Overlay coherence; Datashader treated as a backend | `negotiate()` hands `"auto"` to `auto_negotiate()`; auto collapses an Overlay to one backend (logs, doesn't raise); Datashader is a within-pyqtgraph `scale` strategy, never a registered backend. §3.2, §3.3 |
| N | `scale=` referenced (§2.5 / roadmap) but absent from `Scatter`            | Added `scale: "native"|"auto"|"datashader"` (Phase 1 = native only; auto/datashader honored from Phase 4). §5.1 |

### Currently open

| # | Question                                                                 | Notes                                                                                          |
|---|--------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| O | `DataRef.fingerprint()` policy for reactive/lazy refs (`Signal`, `DataSource`) | Buffer identity is right for static in-memory data, but Signal/DataSource need a version counter or content hash so a changed value re-hashes. Settle when Phase 4 (reactive) lands. §2.1 |
| P | Does `.with_()` keep or regenerate `id`?                                  | Currently **keeps** the id (stable identity through edits; value-equality ignores id anyway). Revisit if Studio needs an explicit "duplicate as a new identity" operation. §2.1 |

New questions go here as they arise during implementation.

## 12. Out of scope for 0.1

To keep Phase 1–6 tight, the following are explicitly deferred:

- 3D rendering (any backend)
- Animation API (`Animation` element type)
- Stream-time plots with auto-rolling windows (a thin convenience on
  top of `Signal` will do for now)
- Cross-backend Overlay (a single Overlay with children rendered by
  different backends and visually composited — hard problem)
- Cluster-distributed datasource (Dask makes sense single-node first)
- Custom shader plugins for pyqtgraph
- Theme inheritance from QPalette during render (one-shot conversion only)
- Update-in-place diffing (Q4 resolved: rebuild always)
- Off-GUI-thread rendering (Capabilities field exists, no impl)

These can be added later without rework if Phase 1 abstractions hold.

## 13. Spec → implementation correspondence

For Phase 1, the concrete files to create, in order (all under the
`src/qtviz/` src-layout, mirroring today's `src/qtwebplot/`):

1. `qtviz/core/_immutable.py` — `_freeze` / `__setattr__` / `with_` /
   `_fields` / `_value_key` / `__eq__` / `__hash__` mixin used by Element,
   Options, Overlay, Layout, Palette. The value-key excludes `id` and
   fingerprints DataRefs (§2.1) so array-backed types stay hashable.
2. `qtviz/data/` — the data layer (§6): `ref.py` (`DataRef`/`TabularRef`/
   `GriddedRef`, `Schema`, `GridData`), `registry.py` (`DataAdapter`,
   `register_data_adapter`, `as_data_ref`), `adapters/` (eager: dict,
   numpy, pandas, arrow). Lazy/gridded adapters (xarray, zarr, dask) and
   the `qtviz.data_adapters` entry-point land in Phase 4–5.
3. `qtviz/core/color.py` — `Color` class, `ColorSpec` union, known
   color names.
4. `qtviz/core/palette.py` — `Palette` class, `from_matplotlib`,
   `from_qt`, `from_hex`, registry.
5. `qtviz/core/options.py` — `Options`, `OverlayOptions`, `LayoutOptions`.
6. `qtviz/core/element.py` — `Element` base, `_next_element_id`.
7. `qtviz/core/compose.py` — `Overlay`, `Layout`, operators, negotiation
   (`negotiate`/`auto_negotiate`, §3.2–3.3), and `LayoutHost` (§3.7).
8. `qtviz/core/event.py` — `Event` types, `EventBus`, throttle (promoted
   `_Throttle`, §2.10).
9. `qtviz/core/threading.py` — `require_gui_thread`, `run_on_gui`, `Worker`.
10. `qtviz/core/backend.py` — `Backend` Protocol, `Capabilities`,
    `RendererRegistry`, `RenderHandle`, `CompositeRenderHandle` (§2.8),
    `RenderContext`.
11. `qtviz/core/view.py` — `View` widget (owns the canonical subscription
    registry, §2.10).
12. `qtviz/core/theme.py` — exists today but needs the `Color`/`Palette`
    migration of §2.13 (breaking, confined — not "minor cleanup").
13. `qtviz/elements/scatter.py` … `spread.py` — the 8 Element types.
14. `qtviz/backends/pyqtgraph/__init__.py` + `render.py` + per-element
    renderers. Hard dep — always registered.
15. `qtviz/backends/__init__.py` — registry, default selection, lazy
    optional backend detection.

This ordering means a working pyqtgraph-only end-to-end
(`View(Scatter(...))`) exists at step 15. Matplotlib backend (Phase 2)
then drops in as a sibling directory; webengine backend (Phase 5)
lands as another sibling. **No file above step 15 changes when adding
a new backend.**

That last sentence is the design's correctness check.
