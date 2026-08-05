# Pane handles — downstream use of individual surfaces (detailed design)

> Deep-dive on the downstream half of `layout-panes-plan.md` ([D147]/[D149]/
> [D150]), written after a code-level investigation of all three backends and
> the host. This document is the implementable design: the pane model, the
> protocol each backend provides, the event/state/export implications, verified
> current-state evidence, a test plan, and sequenced next steps. Design only —
> no code is changed by this document.
>
> Terminology as before: a **surface** is the axes-like render target (pg
> `PlotItem`, mpl `Axes`, one Plotly figure); a **pane** is a Layout slot
> holding one surface tree. A bare `Element`/`Overlay` render is one pane.

---

## 1. Verified current state (evidence, not impressions)

Reproduced offscreen against the current tree:

1. **Per-pane view state is lost — all backends.** Zooming pane 1 of a 2-pane
   pyqtgraph grid to `x=(100, 200)`, then `capture_state()`, returns
   `x_range=(0.0, 1.0)` — pane 0's range. Sites: `PgRenderHandle._vb()` reads
   `self._plots[0]` (`backends/pyqtgraph/render.py:66`); mpl reads
   `self._surfaces[0]` (`backends/matplotlib/render.py:68`);
   `CompositeRenderHandle` inherits the base no-op, so every mixed-backend /
   tabs / splitter / dock view captures **nothing**. Any theme change,
   `set_backend()`, or reactive rebuild silently resets panes 1..n.
2. **Nested homogeneous grids crash.**
   `Layout([Layout([a, b]), c])` with `backend="pyqtgraph"` raises
   `AttributeError: type object 'Layout' has no attribute 'lower'`:
   `_resolve_layout` (`core/_host.py:50`) routes a same-backend grid to the
   backend, but `_render_cell` can only take an Element/Overlay — the nested
   `Layout` falls through to `_render_element`. Nesting works only when the
   LayoutHost happens to take over (mixed backends, splitter/tabs/dock).
3. **Surface identity half-exists, unusably.** `QtvizViewBox` is constructed
   with `surface_id=uuid.uuid4().hex` (`backends/pyqtgraph/render.py:~278`) and
   emits it as `RangeEvent.source_id` / `TapEvent.source_id`
   (`_interaction.py:86,116`). So surface-scoped events *exist* — but the id
   is random, regenerated every render/rebuild, never exposed, and cannot be
   mapped to a pane. mpl keeps a parallel `surface_id` in its surface dicts.
   Meanwhile `SelectEvent`/`PickEvent`/`HoverEvent.source_id` carry *element*
   ids — two identity namespaces already share one field.
4. **Per-pane machinery exists per backend, uniformly shaped, never unified.**
   - pg: ordered `self._plots` (one `PlotItem` per pane, appended in layout
     child order), each with a `QtvizViewBox` that owns selectables and
     already has a public data-space `select_bounds()`.
   - mpl: ordered `self._surfaces` dicts `{"ax", "surface_id", "selectables",
     "y2_ax"?}`, plus an index-addressed programmatic brush
     `select_bounds(ax_index, …)` already on the handle.
   - webengine: `can_host` declares no native grid — every webengine layout
     goes through the LayoutHost, so **each pane is already its own child
     handle** with working single-surface capture/restore (shadow data-space
     ranges in Python — capture is synchronous, no JS round-trip needed).
   - composite: ordered `handle.children`, one child handle per pane.
5. **The View pipeline is single-state.** `View._rebuild` stashes exactly one
   `ViewState` (`core/view.py:314-318`) and `_install` restores it once
   (`view.py:295-297`). Whatever the handles learn to capture, the View
   threads one object through — so the portable record must stay *one object*
   (which may contain many panes).

Reading: the pane concept is present in every layer as a private, index-based,
inconsistently-exploited list. Nothing needs inventing; it needs a **name, a
protocol, and a public seam**.

---

## 2. The design

### 2.1 One sentence

Every render exposes an ordered set of **panes**; a pane has a **stable label**
(user-given via [D145], else its index as a string), and the label is the key
for state capture/restore, event scoping, native access, and export — from
creation to teardown.

### 2.2 The pane protocol (core, `core/backend.py`)

`RenderHandle` gains two members with a base implementation backends override:

```python
class RenderHandle:
    def panes(self) -> tuple[PaneHandle, ...]:
        """One PaneHandle per surface, in layout child order. Base: a single
        pane labeled "0" wrapping the whole handle — every existing and
        third-party single-surface backend is compliant with zero changes."""
    def pane(self, key: str | int | None = None) -> PaneHandle:
        """By label, by index, or the only pane when key is None (raises on
        ambiguity)."""
```

`PaneHandle` is a small abstract class — the "Axes of qtviz", scoped strictly
to **interaction-side** concerns:

```python
class PaneHandle:
    label: str                                  # stable pane identity
    def capture(self) -> ViewState: ...         # data space, incl. y2 ([D88])
    def restore(self, state: ViewState) -> None
    def set_range(self, *, x=None, y=None, y2=None) -> None   # sugar over restore
    def autorange(self) -> None                 # vb.autoRange / ax.autoscale / relayout
    def select(self, x0, y0, x1, y1) -> None    # programmatic brush → SelectEvents
    @property
    def native(self): ...                       # PlotItem | Axes | web host ([D53])
    @property
    def elements(self) -> tuple[str, ...]       # element ids on this surface
    def export(self, fmt, path, *, dpi=None, transparent=False) -> Path  # §2.6
```

Per-backend cost is small because §1.4's lists already exist:

| Backend | PaneHandle wraps | capture/restore | select | native |
|---|---|---|---|---|
| pyqtgraph | one `PlotItem` (+ its `_qtviz_vb2`) | the existing pane-0 logic, generalized (R1 de-log per pane already keyed off each vb's `x_log/y_log`) | `vb.select_bounds` — exists | the `PlotItem` |
| matplotlib | one `_surfaces[i]` dict | existing pane-0 logic, generalized | `emit_bounds_select(surfaces[i], …)` — exists | the `Axes` |
| webengine | the whole (single-surface) handle | existing shadow-range logic — unchanged | honor-or-warn (no brush capability today) | the web host |
| composite | one child handle's `pane(0)`… flattened | delegate | delegate | delegate |

**Flattening rule for nesting:** `panes()` flattens depth-first in child order;
labels must be **globally unique across the tree** (validated at compose time
when labeled layouts nest — a tier-1 check). No dotted paths.

**Staleness contract (same discipline as `native()`):** a `PaneHandle` is a
thin facade over the *current* render. `view.pane(...)` fetches fresh;
a handle kept across a rebuild goes dead — `pane.alive` is the guard, and every
op on a dead pane raises `DisposedError` rather than touching freed widgets.
Nothing is ever cached on the immutable node tree.

**Threading:** every `PaneHandle` method is GUI-thread-only
(`require_gui_thread` on mutators), same rule as all widget mutation.

### 2.3 [D150 detailed] `LayoutState` — the portable multi-pane record

```python
@dataclass(frozen=True)
class LayoutState:
    panes: tuple[tuple[str, ViewState], ...]    # ordered (label, state) pairs
    def get(self, label) -> ViewState | None
```

- **`capture_state()`/`restore_state()` change type** to `LayoutState`. With
  the pane protocol in place both become **base-class implementations written
  once in core**: capture = `{p.label: p.capture() for p in panes()}`; restore
  = match **by label**, silently dropping labels the new render doesn't have.
  Backends delete their handle-level state code entirely (pg/mpl pane-0 logic
  moves into their `PaneHandle.capture`); `CompositeRenderHandle` gets working
  state for free — fixing §1.1 and §1.4's composite hole in one move.
- **`ViewState` is untouched** — it remains the per-surface record, the R1
  data-space rules and `y2_range` unchanged. A single-surface render's
  `LayoutState` has one `"0"` entry.
- **Label-matching is the restore contract.** User labels mean "same label =
  same role", so state survives even a root swap that reorders panes; default
  index-labels degrade to positional matching, which is today's (intended)
  behavior generalized. Unknown labels drop without warning — a changed
  dashboard shape is not an error.
- **View changes**: `_pending_state` and `capture/restore` call sites
  (`core/view.py:314,296`) swap types; the backend-switch path needs nothing
  else — labels are backend-independent, so pg→mpl carries all panes.
- Interplay verified: restoring a pane's range fires the same ViewBox/axes
  signals as a user zoom, so `RasterController` re-aggregation (datashader)
  and `RangeEvent` emission behave identically to interactive panning — no
  special-casing.

### 2.4 [D149 detailed] Pane identity on events

- `Event` gains `pane: str | None` as a **keyword-only defaulted field**
  (`field(default=None, kw_only=True)`) — the kw-only form is required because
  subclasses (`RangeEvent.x`…) declare non-default positional fields after the
  base; a plain default would be a dataclass `TypeError`. Every existing
  constructor call and test stays valid.
- **Stamping happens where the pane boundary is known:**
  - pg/mpl (one handle, many surfaces): `RenderContext` gains `pane: str`
    (it already carries the per-surface `x_scale`/`show_legend`/…); the
    `QtvizViewBox` and the mpl per-surface wiring stamp it on every emit —
    Range/Tap *and* the element events (Select/Pick/Hover) of that surface.
  - LayoutHost (composite): each child bus is wrapped in a stamping shim that
    re-emits with `replace(ev, pane=label)` when `ev.pane is None`. This gives
    **every third-party entry-point backend pane-correct events with zero
    backend changes** — they render one surface; the host knows which pane it
    is. ([D125]'s zero-edits promise holds.)
- **`RangeEvent`/`TapEvent.source_id` becomes the pane label**, replacing the
  per-render random uuid (§1.3). This is strictly more useful and nothing
  could have depended on the uuid; the two-namespace muddle resolves to:
  `source_id` = element id on element events, pane label on surface events;
  `pane` = always the pane. CHANGELOG behavior-change table entry.
- **`View.on` grows the symmetric filter**: `view.on(qv.RangeEvent, cb,
  pane="price")` (str or sequence), composable with `source=` ([D134]); same
  wrapping idiom, one line of filter code.

### 2.5 Nested grids — fix the crash (bug tier, no decision needed)

`_resolve_layout` routes any grid **containing a `Layout` child** to the
LayoutHost (backends' `can_host("grid")` means *flat* grids — which is all
they can actually do, per §1.2). Nested grid = host grid of backend-rendered
sub-grids; with §2.3 the composite chain gives it per-pane state, and with
§2.4 the host shim gives it pane events. One conditional + a regression test.

### 2.6 Per-pane export

- pyqtgraph: `ImageExporter(plotItem)` exports an item subtree — true per-pane
  png from a shared scene. (SVG stays out: backend-wide position, [D72].)
- matplotlib: crop the figure to the axes' tight bbox
  (`bbox_inches=ax.get_tightbbox(…)` transformed to inches) — png/svg/pdf.
  Needs a spike for overhanging artists (suptitle, neighbors' legends);
  fidelity caveats are honor-or-warn, never silent.
- webengine / composite: delegate to the child handle's existing per-figure
  export. Composite root export (whole-container grab, [D72]) is unchanged;
  `pane.export` is the per-pane vector answer [D72] deferred to
  `handle.children[i]` — now with a name instead of an index.

### 2.7 What `PaneHandle` deliberately does NOT do (the immutability boundary)

No `set_title`, no `set_scale`, no `.opts()` — **describe-side config never
flows through the handle.** The declarative answer to "retitle the price pane"
is a new node. To keep that ergonomic, [D145] adds the pure-core copy-with:

```python
layout.with_pane("price", new_node)   # new Layout, one child swapped
view.set_root(view.root.with_pane("price", new_node))
```

(An honest full rebuild — same semantics as `set_root` today; a diffing
fast-path is a separate future item and must not be promised by this API.)
The one-way rule keeps: nodes describe, handles interact, events report.
Rejected again after detailed review: an imperative pane (an object that both
reads state *and* mutates description) — it would fork every surface option
into two sources of truth and break value-hashed rebuild reasoning.

---

## 3. API summary (public-surface delta)

| Name | Kind | Freeze impact ([D82]/[D135]) |
|---|---|---|
| `View.pane(key=None)` / `View.panes` | method / property | api.md + freeze test |
| `PaneHandle` | returned type (like `StreamRef` — importable, not `__all__`) | api.md |
| `LayoutState` | returned type; `capture_state`/`restore_state` signature change | api.md + CHANGELOG behavior table |
| `Event.pane` (kw-only) | field on all events | api.md |
| `View.on(..., pane=)` | keyword | api.md |
| `RangeEvent/TapEvent.source_id` = pane label | behavior change | CHANGELOG behavior table |
| `Layout.with_pane(label, node)` | method (with [D145] labels) | api.md + freeze test |

Everything else in this document is internal (`RenderContext.pane`, the host
stamping shim, backend `PaneHandle` subclasses).

## 4. Test plan

Conformance (parametrized over pyqtgraph / matplotlib / webengine-where-
offscreen-allows / mixed-composite — the house pattern):

1. zoom pane *k* of *n* → `capture_state()` → theme change → every pane's
   range preserved (kills §1.1; the regression that matters most).
2. same across `set_backend("pyqtgraph" ⇄ "matplotlib")` — labels carry state
   across backends.
3. `view.pane("A").capture()` equals the last `RangeEvent` ranges for that
   pane; under `scale="log"` both are data space (R1 per pane).
4. every event from a 2-pane grid carries the right `pane` label — including
   Select/Pick from elements inside a pane, and events crossing the composite
   host shim.
5. `view.on(pane=…)` filtering; composed with `source=`.
6. `pane.select(...)` emits per-element SelectEvents scoped to that pane only.
7. nested grid renders on every backend (regression for §1.2) and its panes
   flatten with unique labels.
8. `pane.export` writes a file per backend (webengine display-gated skip);
   mpl crop contains the pane's title, not its neighbor's.
9. tier-1: `LayoutState` value semantics; label uniqueness validation incl.
   nested; `with_pane`; dead-pane `DisposedError`; base `panes()` compliance
   for a stub single-surface backend (the [D125] zero-edit guarantee).

No new benchmarks: capture/restore is O(panes) of tuple reads; the composite
stamp is one `dataclasses.replace` per event — both far below the [D77]
streaming path this project actually budgets. (Stated per the cadence rule so
the omission is a decision, not an oversight.)

## 5. Next steps (sequenced; each independently shippable, TDD)

> **Status 2026-08-05: S1–S5 all shipped** on `feat/pane-handles` (one commit
> per step, d714377 → ab5a2d3), inside the 2.0 break per the owner call; the
> §6 recommendations were adopted as decided. **The sharing track shipped the
> same day on the same branch (owner go):** [D146] `link_x/link_y ∈ bool |
> "col" | "row"` with cell-derived, span-merging groups (pg `setXLink` per
> group, mpl `sharex` per group leader), and [D151] cross-backend linking via
> a `_LinkController` on the composite handle — RangeEvent-driven
> `pane.set_range` propagation, echo-guarded by a reentrancy flag (sync) plus
> a value guard (async webengine round-trips); nested-layout panes are
> excluded from cross-pane groups with a warning. The host now honors
> `link_x`/`link_y` (`_HOST_LAYOUT_HONORED`).

| Step | Contents | Depends on | Size |
|---|---|---|---|
| **S1 — fix wave** | §2.5 nested-grid routing; pane protocol internal-only (`panes()` on all handles, auto index labels); base-class `LayoutState` capture/restore; View threads `LayoutState`. Conformance tests 1–2, 7. | — | M — the pivotal one |
| **S2 — names** | [D145] as planned: `labels` on `Layout`, list-form mosaic, `Layout.grid(mapping)`, `layout[label]`, `with_pane`; label-keyed state upgrades transparently (auto labels *are* index strings, so S1's records stay valid). | S1 | S–M, pure core |
| **S3 — the public pane** | `PaneHandle` surface per §2.2 (`view.pane/panes`, capture/restore/set_range/autorange/select/native/elements); staleness guard. Tests 3, 6, 9. | S1 (S2 for names) | M |
| **S4 — pane events** | §2.4: `Event.pane`, `RenderContext.pane`, host stamping shim, `source_id` semantic fix, `View.on(pane=)`. Tests 4–5. | S2 | M |
| **S5 — per-pane export** | §2.6, spikes first (pg item-export, mpl bbox crop). Test 8. | S3 | S + 2 spikes |

The sharing track from `layout-panes-plan.md` ([D146] `link_x="col"/"row"`,
[D151] cross-backend linking gate) is unchanged and slots after S4 — [D151]
consumes S4's pane-stamped `RangeEvent`s.

**Sequencing vs the 2.0 arc (owner call):** this work is file-adjacent to the
2.0 waves (compose/options/event/backends) and includes CHANGELOG-visible
behavior changes (`capture_state` type, `RangeEvent.source_id`). Recommended:
land it **inside the 2.0 clean break** — after wave 5's freeze flip, as its own
wave — so users absorb one breaking release, not two, and `FROZEN_2_0` is
amended once. S1 (pure bug fixes, no public surface) can land any time,
including before the arc.

## 6. Open calls for the owner

1. `RangeEvent.source_id` → pane label (recommended) vs keeping a parallel
   uuid field for compatibility nobody can be using.
2. `pane.set_range(x=…, y=…)` sugar on the handle (recommended) vs
   capture/restore only — the one place imperative-feeling verbs are allowed,
   because they mutate *interaction* state (same class as a user drag), never
   description.
3. `with_pane` naming (`with_pane` vs `set_pane` vs `__setitem__`-rejected) —
   recommend `with_pane`, matching the `AxisSpec.with_(…)` house idiom.
4. Sequencing per §5 — inside the 2.0 break (recommended) or as a follow-on
   0.x wave.
