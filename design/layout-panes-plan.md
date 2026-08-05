# Plan — plot organization: panes as first-class citizens

> **Focus question.** matplotlib users organize figures with `GridSpec` /
> `subplots` / `subplot_mosaic` and then *keep working with each `Axes`* —
> configure it, query it, attach callbacks to it, export it. What is the qtviz
> equivalent, how good is it today, and what should improve so that (a) creating
> a multi-pane arrangement is as easy as possible and (b) each pane remains
> **usable downstream** after render?
>
> Investigation + plan only — no code is changed by this document. Proposals are
> numbered [D145]–[D151] for the discussion-items register. Companion to
> `axis-surface-feasibility.md` (the per-surface config seam this builds on) and
> `2.0-mark-ir-and-surface.md` §[D133] (`.opts()`).
>
> **Follow-up:** the downstream-use half ([D147]/[D149]/[D150]) is designed in
> detail in [`pane-handles.md`](pane-handles.md), which supersedes §3.3/§3.5/
> §3.6 and the §4 phasing for that track (its S1–S5 steps replace P1/P3 here).

**Terminology.** qtviz's analogue of a matplotlib `Axes` is a **surface** — the
thing one `Overlay` (or bare `Element`) renders into: a pyqtgraph `PlotItem`, an
mpl `Axes`, a Plotly figure. A **pane** is a slot in a `Layout`. In a grid the
two coincide one-to-one; tabs/splitter/dock panes also each hold one surface
tree. This document uses *pane* for the layout slot and *surface* for the
axes-like render target.

---

## 1. Current state — review

### 1.1 Creation (describe side) — already good, three gaps

What exists is genuinely competitive with matplotlib on the *describe* side:

| Need | matplotlib | qtviz today |
|---|---|---|
| quick grid | `plt.subplots(2, 2)` | `(a + b + c + d).opts(cols=2)` |
| spans + holes | `subplot_mosaic("AAB\nCCB")` | `Layout.mosaic("AAB;CCB", A=…, B=…, C=…)` ([D108]) |
| ratios | `width_ratios=` / `height_ratios=` | `LayoutOptions.width_ratios/height_ratios` |
| shared axes | `sharex=True/'col'/'row'` | `link_x=True` (all-or-nothing bool) |
| per-axes config | `ax.set_title(…)` after creation | `child.opts(title=…)` before composition ([D133]) |
| nesting | `subgridspec` / `subfigures` | `Layout` children may be `Layout`s |
| beyond-figure chrome | — (Qt not mpl's job) | tabs / splitter / dock kinds — qtviz's unique strength |

One shape-decider (`grid_geometry`, `core/compose.py:240`) feeds all three
consumers (mpl figure, pg layout, Qt host), so a given `Layout` has the same
shape everywhere. That invariant is worth protecting through everything below.

The gaps:

1. **Mosaic labels are single characters and then discarded.** `parse_mosaic`
   walks the string character-by-character (`compose.py:48`), so a pane can't be
   called `"price"` or `"volume"` — and after construction the labels don't
   exist at all: `Layout` stores only an ordered `children` tuple + `cells`.
   Nothing downstream can ever address "the price pane" by name because the name
   is gone by the time `Layout.__init__` runs.
2. **Axis sharing is all-or-nothing.** `link_x: bool` links *every* pane to pane
   0 (`pyqtgraph/_axes.py:9`). matplotlib's `sharex='col'` / `'row'` — the
   common dashboard case (columns of time-aligned plots) — is not expressible.
   And linking "doesn't cross mixed-backend panes" (`core/_host.py:68`) —
   silently, not warned.
3. **Programmatic spans need hand-built `cells=`.** The ASCII mosaic is great
   interactively, but building an n-pane grid with spans in a loop means
   constructing `(row, col, rowspan, colspan)` tuples by hand against an
   undocumented constructor argument. (matplotlib's answer is `gs[0, :]`
   slicing; §3.4 takes a different route.)

### 1.2 Downstream use (per-pane, post-render) — the real weakness

This is where qtviz is far behind `fig.axes` / the mosaic label→`Axes` dict:

1. **Per-pane view state is silently lost.** `ViewState` is a single-surface
   record, and every backend captures **only pane 0**:
   - pyqtgraph: `capture_state` reads `self._plots[0]` (`pyqtgraph/render.py:66`);
   - matplotlib: `self._surfaces[0]` (`matplotlib/render.py:68`);
   - `CompositeRenderHandle` (mixed backends / tabs / splitter / dock) doesn't
     override `capture_state` at all → returns an empty `ViewState`.
   Consequence: in any multi-pane view, pan/zoom on panes 1..n **does not
   survive** a theme change, a `set_backend()` switch, or a reactive rebuild —
   pane 0 restores, the rest snap back to autorange. This is a [D2]
   ("state survives backend switches") violation in spirit, and it is silent —
   the project's top diagnosed weakness class.
2. **No way to address a pane after render.** The escape hatches are
   element-scoped (`view.native(element_id)`, `handle.native(...)`) or
   backend-private (`PgRenderHandle._plots`, mpl `_surfaces`,
   `CompositeRenderHandle.children` — index-based, composite-only). There is no
   uniform "give me pane *k* / pane `'price'`" that yields the surface's native
   object, its current ranges, or a scoped export. matplotlib users do this
   constantly; qtviz users must know which backend they're on and reach into
   underscored attributes.
3. **Events carry element identity, not pane identity.** `Event.source_id`
   names the emitting *element* (`core/event.py:22`); `view.on(..., source=el)`
   filters by it ([D134]). Fine for picks — but a `RangeEvent` is a *surface*
   fact, and "which pane did the user zoom?" requires the caller to keep their
   own element→pane bookkeeping. Pane-scoped subscription (`view.on(...,
   pane="price")`) doesn't exist.
4. **Per-pane export is uneven.** Composite handles export one raster of the
   whole container ([D72]) and point at `handle.children[i].export(...)` for
   vector panes — but a *homogeneous* pyqtgraph grid is one scene under one
   handle, so per-pane export doesn't exist there at all.

### 1.3 Root-cause reading

The describe side got real design attention ([D108] mosaic, ratios, the [D133]
`.opts()` wave). The *handle* side stayed element-granular (`native(element_id)`,
`source=`) because Phase-1 interaction work predated multi-pane emphasis; the
surface became an explicit concept in the axis-surface seam (`surface_of`,
`apply_surface`) but only on the **describe/apply** path — it never got an
identity on the **handle/event** path. Everything in §1.2 is the same missing
concept: *a surface has no name and no handle*.

---

## 2. matplotlib review — what to borrow, what to reject

**Borrow:**

- **The mosaic dict return.** `subplot_mosaic` returns `{label: Axes}` — the
  label you drew in ASCII is the key you use forever after. This
  label-stability from creation through downstream use is the single best idea
  in matplotlib's layout API and is exactly what §1.2(2) lacks. Their list-form
  spec (`[["left", "right_top"], ["left", "bottom"]]`) also lifts the
  single-character restriction.
- **`sharex='col' | 'row'`** — the vocabulary for structured sharing.
- **Axes as the unit of query/config after creation** — but adapted (see below):
  qtviz's post-render pane object should expose *interaction state and escape
  hatches*, not describe-side mutation.

**Reject (with reasons):**

- **Imperative attachment** (`fig.add_subplot`, `ax.plot(...)`) — the element
  tree is immutable data; render attaches. Nothing to change.
- **A mutable `GridSpec` object + slicing** (`gs = GridSpec(3,3); ax =
  fig.add_subplot(gs[0, :])`). A stateful builder contradicts the immutable
  value-hashed node algebra, and the mosaic (string or list form) expresses the
  same shapes declaratively. The programmatic case gets a documented,
  validated `cells=` instead (§3.4).
- **The constrained-layout / tight-layout solver.** matplotlib needs one
  because it owns text metrics inside a dumb canvas; qtviz sits on Qt layouts
  (stretch factors, size hints) and pyqtgraph/Plotly do their own label
  spacing. Non-goal.
- **`SubFigure`** — nested `Layout` already covers it.
- **`twinx()` as an axes-spawning call** — qtviz already has the declarative
  `axis="y2"` + `y2=` AxisSpec ([D88]/[D133]); no second mechanism.

---

## 3. Proposal

Four decisions on the describe side, three on the handle side. The through-line:
**a pane gets a name at creation and keeps it through render, state, events, and
export.**

### 3.1 [D145] Named panes — labels become part of `Layout`

`Layout` gains an optional `labels: tuple[str, ...] | None` (aligned with
`children`, validated same-length + unique, value-hashed like everything else).
Every pane always has an *effective* label: the given one, else its index as a
string (`"0"`, `"1"`, …) — so unlabeled flow layouts participate in everything
below without ceremony.

Creation surfaces that produce labels:

```python
# mosaic — string form keeps working; labels are now RETAINED
qv.Layout.mosaic("AAB;CCB", A=a, B=b, C=c)          # labels = ("A", "C", "B")

# mosaic — list form lifts the single-char limit (subplot_mosaic precedent)
qv.Layout.mosaic([["price",  "book"],
                  ["volume", "book"]], price=p, volume=v, book=ob)

# grid from a mapping — the "named subplots" one-liner
qv.Layout.grid({"price": p, "volume": v}, cols=1)
```

- List-form cells obey the same solid-rectangle rule; `None` (or `"."`) is a
  hole. `parse_mosaic` generalizes from `str` to `str | Sequence[Sequence[str
  | None]]`; the `Cell` geometry and `grid_geometry` are untouched.
- `layout["price"]` / `layout.pane("price")` returns the child node
  (pre-render addressing — useful for tests and for rebuilding one pane via a
  reactive root).
- `+` on a labeled/mosaic layout keeps today's nest-don't-append sealing rule.
- `tab_labels` folds in: `Layout.tabs({"Raw": a, "Fitted": b})` gives tab
  captions *and* pane labels from one spec (the separate `tab_labels` option
  stays for the positional form).

### 3.2 [D146] Structured sharing — `link_x: bool | "col" | "row"`

Widen the existing fields (no rename — `link_x`/`link_y` are established house
vocabulary): `True` = all panes (today's behavior, unchanged), `"col"` = link
within each grid column, `"row"` = within each row. Grouping is computed from
`grid_geometry` cells, so it composes with mosaic spans (a spanning pane joins
the group of every column/row it covers — matplotlib's rule). Non-grid kinds
reject `"col"/"row"` at construction.

Mixed-backend panes: linking is currently *silently* skipped by the host. That
becomes a one-time honor-or-warn `QtvizWarning` ([D51] discipline) now, and
§3.7 sketches the real fix later.

### 3.3 [D147] `PaneHandle` — the downstream unit ("the Axes of qtviz")

The core of the plan. `View` (and `RenderHandle`) expose panes by label or
index:

```python
view = qv.View(layout)
pane = view.pane("price")          # PaneHandle; view.panes → tuple of all

pane.label                         # "price"
pane.state                         # ViewState — data-space, live (R1 rules apply)
pane.restore_state(ViewState(x_range=(0, 10)))   # programmatic pan/zoom
pane.native                        # pg PlotItem | mpl Axes | webengine host — [D53] escape valve
pane.export("price.svg")           # per-pane export where the backend can (§3.6)
pane.elements                      # ids rendered on this surface (feeds source= filters)
```

Design constraints, mirroring [D53]:

- `PaneHandle` is a **thin live facade over the current render**, fetched from
  the handle each time (`view.pane(...)` never caches across rebuilds — like
  `view.native()`, it reflects the current render or raises/returns a dead
  marker after a rebuild). It is *not* a node: describe-side config stays
  `.opts()` on the child before composition. No mutation of the immutable tree
  through it, ever.
- Backend cost is small because the lists already exist: pg `_plots`, mpl
  `_surfaces`, webengine per-figure hosts, composite `children`. The work is a
  uniform protocol — `RenderHandle.pane_count` / `pane(i)` — plus the
  label↔index map, which comes straight from the rendered `Layout` (labels ride
  the node, [D145]).
- A single-surface render (bare element / overlay) is one pane, label `"0"` —
  no special-casing for the common case; `view.pane()` with no argument returns
  it.
- Nested layouts flatten in child order for indexing; labels address panes at
  any depth (dotted paths rejected — inner labels must be globally unique,
  validated at compose time when nesting labeled layouts).

### 3.4 [D148] Programmatic grids — promote `cells=` to a documented surface

For loop-built dashboards, `Layout.grid` accepts explicit cells, validated by
the same overlap/solidity checks the mosaic parser applies:

```python
panes  = {f"ch{i}": make_channel(i) for i in range(8)}
cells  = {f"ch{i}": (i, 0, 1, 1) for i in range(8)} | {"summary": (0, 1, 8, 1)}
qv.Layout.grid(panes | {"summary": s}, cells=cells)
```

This is deliberately the *whole* answer to GridSpec slicing: a dict of
`(row, col, rowspan, colspan)` keyed by label, symmetric with the mosaic's
output, no mutable builder object. (Evaluated and rejected: `gs[0, :]`-style
sugar — a second, stateful way to say the same thing.)

### 3.5 [D149] Pane identity on events

`Event` gains `pane: str | None = None` (frozen-dataclass default keeps every
existing constructor call and test valid). Backends stamp it where the surface
is known at wiring time (they already thread per-surface context to wire
events). `View.on` grows the matching filter, symmetric with `source=`:

```python
view.on(qv.RangeEvent, on_zoom, pane="price")
view.on(qv.SelectEvent, on_brush, source=scatter)   # element-scoped, unchanged
```

`RangeEvent` from a pane finally answers "which pane?" without user-side
element→pane bookkeeping. This is also the enabling piece for cross-backend
linking (§3.7).

### 3.6 [D150] Per-pane state and export — fix the silent loss

- **`capture_state()`/`restore_state()` become all-pane.** The portable record
  is a `LayoutState`: an ordered mapping of pane label → `ViewState` (a
  single-surface render is the 1-entry mapping — `ViewState` itself is
  unchanged, so nothing breaks). Every backend captures/restores each surface;
  `CompositeRenderHandle` implements it by delegating to children. Restoration
  matches by **label**, so state survives even a root swap that reorders panes,
  and degrades gracefully (unknown labels dropped) when the new root differs.
  This converts §1.2(1) from silent data loss to the documented [D2] guarantee,
  now per pane.
- **`pane.export(...)`** — mpl: render the one `Axes` region (bbox_inches on
  the axes' tightbbox); pyqtgraph: `ImageExporter(plotItem)` scoped to the
  item (works per-pane in one scene); webengine: per-figure export exists.
  Where a backend can't, honor-or-warn — never silently export the whole
  figure.

### 3.7 [D151] Cross-backend linking (gated follow-on)

With [D146] groups + [D149] pane-stamped `RangeEvent`s, mixed-backend linking
becomes an event-bus loop: a `RangeEvent` from a pane in a link group →
`restore_state` on the group's other panes (guarded against echo by a
same-range check). Sequenced last and gated behind its own go/no-go because the
feedback-loop and throttling risk is real (webengine round-trips are async).
Until it lands, the [D146] warning covers honesty.

---

## 4. Phasing (each independently shippable, TDD per house cadence)

| Phase | Contents | Nature |
|---|---|---|
| **P1 — stop the silent loss** | [D150] all-pane capture/restore incl. composite; conformance test: zoom pane 2 of 3 → theme change / backend switch → range preserved, on every backend | bug-fix tier; no new public names beyond `LayoutState` |
| **P2 — names** | [D145] labels on `Layout`, list-form mosaic, `Layout.grid(mapping)`, `layout[label]`; [D148] documented `cells=` | describe-side, pure core, tier-1 testable |
| **P3 — the pane handle** | [D147] `PaneHandle` + `view.pane()/panes`; [D149] `Event.pane` + `view.on(pane=)`; [D150] per-pane export | the downstream payoff; conformance: same `pane("A").state` semantics across backends |
| **P4 — sharing** | [D146] `link_x="col"/"row"` + mixed-pane warning; then the [D151] gate decision | independent of P3 |

Ordering rationale: P1 is a correctness fix worth shipping alone. P2 before P3
because the handle addresses panes *by the labels P2 creates*. P4 is
parallelizable after P2 (needs `grid_geometry` grouping only).

**Freeze obligations ([D82]/[D135]):** new public names (`LayoutState`,
`PaneHandle`, the widened `Layout.grid`/`mosaic` signatures, `Event.pane`,
`View.pane`/`panes`, `link_x` union) each require the `test_api_freeze.py` +
`docs/api.md` + `CHANGELOG.md` triple in the same commit. `.opts()` keyword
unions (`link_x`) also touch the [D133] surface tables.

## 5. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Label-matched state restore across a *changed* root guesses wrong (same label, different plot) | labels are user-chosen names — same-label = same-role is the contract; document; unknown labels drop silently by design |
| R2 | `Event.pane` stamping is missed on some emit path (webengine JS bridge) | conformance test parametrized over backends: every `RangeEvent` from a 2-pane grid carries the right label |
| R3 | pyqtgraph per-pane export from a shared scene clips neighbors | `ImageExporter` on the `PlotItem` bounds — spike first; degrade honor-or-warn if fragile |
| R4 | `PaneHandle` staleness after rebuild (holds dead widgets) | fetch-fresh contract (§3.3) + a `pane.alive` guard, same discipline as `native()` |
| R5 | [D151] feedback loops across async webengine panes | separate gate; echo-guard + throttle; not in P1–P4 scope |

## 6. Deliberately not proposed

No mutable `GridSpec` builder or slicing sugar; no imperative `pane.add(...)`
attachment; no layout solver (Qt owns sizing); no `SubFigure` (nested `Layout`
stands); no per-pane `.opts()` on `PaneHandle` (describe-side config stays on
the node — one direction of data flow); no change to `Overlay`/surface
semantics or the [D129]–[D133] vocabulary.
