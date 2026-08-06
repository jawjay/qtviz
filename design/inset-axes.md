# Design note — inset axes

> **Question.** How would qtviz incorporate matplotlib-style inset axes
> (`ax.inset_axes` + `indicate_inset_zoom`) — the last structural gap from the
> plot-organization comparison (`layout-panes-plan.md` §2) worth closing?
>
> **Short answer.** As a **structural element** — `qv.Inset(child, rect=…)` —
> composed into an overlay like an annotation (`parent * Inset(...)`), rendered
> natively per backend (all three have a native mechanism), and — the part
> that makes it more than parity — registered as a **pane** ([D147]): a
> labeled inset gets state capture/restore, `view.pane("zoom").set_range`,
> pane-scoped events, and per-pane export *for free* from the existing
> machinery. A portable, stateful, event-scoped inset is something matplotlib
> itself doesn't have.
>
> Thinking-through only — no code is changed by this note. Proposals numbered
> [D152]–[D154]. Companion to `pane-handles.md` (whose machinery this rides).

---

## 1. What matplotlib provides (the target semantics)

- `ax.inset_axes([x0, y0, w, h])` — a child Axes floating on a parent, placed
  in **axes-fraction** coordinates (data-coords via `transform=` also exist).
  A full Axes: any artist renders into it. Canonical uses: zoom insets,
  mini-overviews, small context panels.
- `ax.indicate_inset_zoom(axins)` — a rectangle on the parent marking the
  inset's view region, plus connector lines to the inset's corners.

## 2. The qtviz shape — [D152] `Inset` as a structural element

```python
overview = qv.Curve(d, x="t", y="v")
zoom     = qv.Curve(d, x="t", y="v").opts(x=qv.AxisSpec(lim=(12.0, 14.0)))

plot = overview * qv.Inset(zoom, rect=(0.55, 0.55, 0.4, 0.4),
                           label="zoom", indicate=True)
```

- **Node position:** an `Inset` rides an `Overlay`'s children like an
  annotation does — `series_index_map` already treats annotation-class
  children as chrome (no palette slot); `Inset` joins that class. `a *
  Inset(...)` keeps the algebra: immutable, value-hashed (the child node
  hashes like any node), `.opts()`-composable on both parent and child.
- **Fields:** `child: Node` (Element or Overlay — the inset's own surface,
  with its own `OverlayOptions`/`AxisSpec`s), `rect: (x0, y0, w, h)` in
  **axes-fraction** of the parent's plot area (validated ⊆ sane bounds;
  data-coordinate placement deferred, §6), `label: str | None` (pane
  identity, §4), `indicate: bool = False` (§5), plus a themed frame border.
- **Why an element and not an Overlay field:** one composition idiom
  (`*`) instead of a parallel `insets=` channel; repr/inspection for free;
  and the annotation precedent means backends already have the "chrome
  child" branch to hang it on.
- **Two pipeline touches, declared not duck-typed:**
  1. `resolve_node` dispatches on `DATA_KIND`; `Inset` is `"none"` at its own
     level but its `child` must resolve — one explicit recursion branch
     (`Inset.child` → `resolve_node(child)`, copy-with), mirroring the
     Overlay/Layout branch. `node_is_lazy` recurses the same way.
  2. `auto_negotiate`'s intersect-first rule ([D4]) must include inset-child
     elements: an inset lives **on the parent's surface**, so it is
     single-backend by construction — `_elements_of` learns to yield through
     `Inset.child`.
- **Honesty:** `Inset` cannot lower — it is a sub-*surface*, not marks — so it
  is a head element handled natively per backend, like the surface machinery
  (twin axes) before it. Degradation is per-backend, visible, never silent
  ([D51]): a backend that can't draw insets yet (webengine at first)
  **warns and skips the inset**, parent rendering normally; a backend that
  has never heard of insets fails `supports()` → a loud negotiation error.
  (Part II drops the earlier `Capabilities.insets` flag idea — the render
  path itself is the capability.)

## 3. Per-backend rendering (all three have a native mechanism)

| Backend | Mechanism | Effort / risk |
|---|---|---|
| matplotlib | `ax.inset_axes(rect)` — exactly our semantics; `apply_surface`/`apply_theme_ax` run on the inset ax like any surface | **low** |
| pyqtgraph | a child `PlotItem` (with a `QtvizViewBox`) added to the parent plot's scene, geometry = `rect` × the parent viewbox's pixel rect, recomputed on the parent's `geometryChanged`/resize signal | **medium** — the geometry-tracking hook is the one novel piece; everything inside the inset (renderers, events, R1 log handling) is the existing `_render_cell` re-entered with the inset plot as target |
| webengine (Plotly) | Plotly's native inset idiom: a second axis pair with `domain` fractions (`xaxis2: {domain: [0.55, 0.95]}`) and the child's traces bound to it | **medium-high** — `_figure.py` currently builds exactly one axis pair; adding axis2 touches the translator, relayout parsing (`xaxis2.range` events), and the R1 log map. The riskiest backend; can ship one release behind a capability gate without breaking "describe once" (it *warns*) |

The render path is re-entrant by design: each backend's `_render_cell`
already takes "a node + a surface target"; rendering an inset is calling it
again with the inset's child and the inset's native surface. Theming, surface
config, legends, and event wiring all come along unchanged.

## 4. [D153] An inset is a pane — the payoff

This is where qtviz would exceed matplotlib rather than chase it. A labeled
inset joins the pane protocol:

- `flat_pane_labels` learns to walk `Inset` children inside overlays (keeping
  the single source of pane identity; global uniqueness validated as today —
  an unlabeled inset gets a flat index). The backends' `plots`/`surfaces`
  lists append the inset's surface, so the existing alignment invariant holds.
- Everything then rides for free, no new machinery:
  - **State** ([D150]): the inset's view window is in `LayoutState` — a zoom
    region **survives rebuilds, root swaps, and backend switches**.
  - **Programmatic control** ([D147]): `view.pane("zoom").set_range(x=…)`
    moves the zoom window; `autorange()`, `select()`, `.native`, `.elements`.
  - **Events** ([D149]): pan/zoom *inside* the inset (pg's child
    `QtvizViewBox` gets interaction for free; input hit-tests the top item,
    so inset gestures don't pan the parent) emits `RangeEvent(pane="zoom")`;
    `view.on(..., pane="zoom")` scopes to it.
  - **Export**: `view.pane("zoom").export(...)`.
- Cross-machinery check: the [D151] link controller keys groups by pane
  label, so an inset could even be *linked* to another pane — not a goal,
  but nothing forbids it and nothing breaks.

## 5. [D154] The zoom indicator

`indicate=True` draws the parent-side rectangle marking the inset's current
x/y window.

- **v1 — static:** drawn at render from the inset surface's declared
  `AxisSpec.lim` (the 90% case: a declared zoom window). Implementation is
  nearly free: the rectangle is data-space on the *parent* — exactly what the
  existing `Rect` annotation lowering draws; the renderer synthesizes one.
- **v2 — live:** a small `_InsetIndicator` controller (the
  `RasterController`/`_LinkController` house pattern): subscribe
  `RangeEvent(pane=<inset label>)` → update the parent's rectangle natively
  (pg: move the `QGraphicsRectItem`; mpl: update the artist + `draw_idle`;
  web: `relayout` a shape). Echo-safe trivially (it only *reads* events).
- **Connector lines: deliberately not proposed.** They need the inset's
  *screen* position in the parent's *data* space — not expressible as
  data-space marks, so they'd be per-backend chrome with visible parity
  drift. matplotlib-only connectors would violate "describe once"; skipping
  them uniformly keeps it honest. Revisit only if demand shows up.

## 6. Deliberately deferred / rejected

- **Data-coordinate `rect`** — deferred: placement must then re-layout on
  every parent range change (another controller); axes-fraction covers the
  canonical uses.
- **Insets inside insets** — rejected (depth 1, validated).
- **Mixed-backend insets** — rejected: same surface ⇒ same backend, by the
  same rule as overlays.
- **Drag-to-move/resize insets** — rejected for now; `rect` is description.
- **Inset as a `Layout` concern** — rejected: wrong altitude; an inset is a
  per-surface fact, panes are layout facts.

## 7. Sequencing & obligations

| Step | Contents | Notes |
|---|---|---|
| **I1** | `Inset` node: validation, resolve/negotiation recursion, `Capabilities.insets` | pure core, tier-1 |
| **I2** | mpl + pyqtgraph renderers (webengine gated w/ warn), theme/frame, conformance ("inset renders; child draws; parent unaffected; unsupported backend warns-and-skips") | the pg geometry hook is the one spike |
| **I3** | [D153] pane integration + tests (inset state survives a backend switch; pane-scoped events from inside the inset) | mostly wiring, big payoff |
| **I4** | [D154] static indicator; live-indicator controller as a follow-on gate | |
| **I5** | webengine domain-axes work → lift the gate | riskiest; independently shippable |

Freeze/docs: `Inset` is a new public element → `FROZEN_2_0` amendment +
`api.md` + CHANGELOG in one commit ([D82]/[D135]); `HONORED_NATIVE`
declaration (`rect`, `label`, `indicate`); no benchmarks (render-time only —
stated so the omission is a decision).

Open owner calls: (1) element-flavored `qv.Inset` via `*` (recommended) vs an
`Overlay.insets=` field; (2) ship I1–I3 with webengine gated (recommended) vs
holding for all-three parity; (3) `indicate` rectangle-only forever
(recommended) vs backend-native connectors where available.

---

# Part II — concrete technical plan

> **Status 2026-08-05: I1–I4 shipped** on `feat/inset-axes` (one commit per
> step + an opacity fix; gallery example `38_inset_zoom.py`). I3 needed no
> production changes beyond I2 — the pane machinery carried insets as
> designed. **I5 (webengine domain axes) remains gated** behind the warn-skip
> and awaits its own go.

Written after the code-level walkthrough; adopts the §7 recommendations
(element via `*`; webengine gated behind a warn-skip; rectangle-only
indication) — flag before I1 lands if any should flip. Steps I1–I5 are
independently shippable, TDD per house cadence.

## I1 — the `Inset` node (core; tier-1; public-surface commit)

**`src/qtviz/elements/inset.py`** (new):

```python
class Inset(Element):
    DATA_KIND = "none"                 # data-less at its own level ([D124])
    STRUCTURAL_CHILD = "child"         # declared child-node field (see below)
    HONORED_NATIVE = frozenset({"rect", "label", "indicate"})

    def __init__(self, child: Node, *, rect: tuple[float, float, float, float],
                 label: str | None = None, indicate: bool = False,
                 id: str | None = None) -> None: ...
```

- Validation: `rect` is `(x0, y0, w, h)` axes-fraction — `w, h > 0`,
  `-0.5 <= x0, y0 <= 1.5` (matplotlib permits slight out-of-axes placement;
  clamp-free but bounded); `child` is Element/Overlay (never Layout); **depth
  1**: walking `child`'s overlay children for another `Inset` raises
  `ValidationError`. `label` non-empty when given.
- **`Element.STRUCTURAL_CHILD: str | None = None`** on the base — the [D124]
  declared (not duck-typed) marker for "this data-less element carries a
  child node". Consumed by:
  - `data/pipeline.py::resolve_node` — before the `kind == "none"`
    passthrough: if `STRUCTURAL_CHILD` is set, return
    `node.with_(child=resolve_node(node.child))` (with_ preserves `id`).
    `node_is_lazy` recurses the same way.
  - `core/compose.py::_elements_of` — yield the Inset **and** recurse into
    its child, so `auto_negotiate`'s intersect-first rule ([D4]) covers inset
    contents and `negotiate`'s explicit-backend check errors early on an
    unsupportable child.
- `series_index_map` (`core/compose.py`): Inset joins the chrome class —
  concretely, the check becomes `isinstance(el, ANNOTATION_TYPES) or
  getattr(el, "STRUCTURAL_CHILD", None)` (annotations import stays lazy).
  No palette slot, no shift of following series; `legend_entry()` → `None`.
- Exports: `qtviz/__init__` + **`FROZEN_2_0` + `docs/api.md` + CHANGELOG in
  the same commit** ([D82]/[D135]).
- No `Capabilities.insets` flag: the degradation story is per-backend
  (I2's webengine warn-skip); a third-party backend that never learns about
  insets fails `supports()` → loud negotiation error, which is honest.

Tier-1 tests (`tests/qtviz/test_inset.py`): validation matrix (rect bounds,
depth-1, empty label, Layout child rejected); value-hash (rect/label/child
participate); resolve pipeline (a column-accessor child resolves; lazy child
→ `node_is_lazy` True); negotiation (`_elements_of` yields child elements;
auto excludes a backend that lacks a child element type).

## I2 — renderers (pg + mpl native; webengine warn-skip)

**Interception point — the overlay children loop, not the renderer
registry.** Both native backends special-case Inset exactly where the y2
branch already lives, because the loop scope has everything an inset needs
(plot/ax, theme, bus, plots/surfaces, natives, labels). `supports()` gains
one clause on pg/mpl: `or issubclass(element_type, Inset)` (the registry
conformance test iterates registry types only — unaffected).

**Label threading (shared, exact):** `_render_into` already computes
`labels = flat_pane_labels(node)`; it becomes a `deque` — each
`_render_cell` **pops one** for itself, and pops one more per Inset it
renders, in child order. Depth-first pop order is identical to I3's
`flat_pane_labels` walk by construction, so the plots/surfaces lists stay
aligned with pane identity (the existing defensive length check keeps
guarding it).

- **matplotlib** (`backends/matplotlib/render.py`) — the easy one, ~15 lines:

  ```python
  if isinstance(element, Inset):
      iax = ax.inset_axes(element.rect)      # axes-fraction, native
      self._render_cell(element.child, iax, theme, raw_bus, surfaces,
                        natives, labels.popleft())
      natives[element.id] = iax
      continue
  ```

  `_render_cell` re-entry gives the inset theming, `apply_surface`
  (title/lims/scales), legends, `connect_range`/`connect_brush`, the surf
  dict, and PaneBus stamping — all free. (`raw_bus`: pass the bus the cell
  was handed; `PaneBus` stamps only when `pane is None`, so the inset's
  inner proxy wins and re-wrapping is idempotent.)

- **pyqtgraph** (`backends/pyqtgraph/render.py`) — refactor + the one spike:
  1. Split `_render_cell` into cell creation (grid `addPlot`) and
     `_populate_plot(node, plot, vb, theme, bus, plots, natives, label)`
     (surface apply + y2 + element loop + legend + `_qtviz_element_ids`).
     Grid cells and insets both call `_populate_plot`.
  2. `_render_inset(inset, parent_plot, ...)`:
     `vb = QtvizViewBox(bus=PaneBus(bus, label), surface_id=label, ...)`;
     `iplot = pg.PlotItem(viewBox=vb)`; `iplot.setParentItem(parent_plot)`;
     `iplot.setZValue(parent + 1)`; geometry from
     `parent_plot.vb.geometry()` × rect fractions, recomputed on the parent
     ViewBox's `sigResized` (**the spike** — verify offscreen geometry and
     resize tracking before building on it; budget half a day, fall back to
     `sigRangeChanged`+`geometryChanged` if `sigResized` proves unreliable);
     then `plots.append(iplot)` and `_populate_plot(inset.child, iplot, …)`.
     `style_plot` + a themed border (`iplot` frame pen = theme foreground at
     low alpha) so the inset reads as a panel over data.
- **webengine** (`backends/webengine/_figure.py`): the trace-build loop
  skips `Inset` children with a **warn-once** `QtvizWarning`
  (`"webengine: inset axes not supported yet; inset {label!r} skipped"`),
  parent renders normally. `supports()` clause added like pg/mpl so
  negotiation still allows explicitly-chosen webengine. Headless-testable:
  the built figure dict contains no inset traces + the warning fires.

Tier-2 tests (parametrized pg/mpl): inset renders (native exists, parent's
own element count unchanged); inset surface options honored (mpl:
`iax.get_xlim() == lim`; pg: vb range == lim); nested-in-grid (an inset
inside a mosaic pane); webengine figure-dict skip + warning (headless).

## I3 — insets are panes ([D153]; the payoff, mostly wiring)

- `core/compose.py::flat_pane_labels`: after appending a leaf's label, walk
  the leaf's overlay children (`n.children if isinstance(n, Overlay) else
  (n,)`) for `Inset` elements and append `inset.label` (or flat index) —
  depth-first, matching I2's pop order. Uniqueness validation unchanged
  (inset labels join the same namespace). Lazy `elements` import, as
  `series_index_map` already does.
- Backends: **nothing** — I2 appended the inset plot/surf to the exact lists
  `_panes()` zips with `flat_pane_labels`, and `PgPane`/`MplPane` wrap inset
  surfaces indistinguishably.
- Everything downstream is inherited: `LayoutState` (inset zoom window
  survives rebuild/backend switch), `view.pane("zoom").set_range/autorange/
  select/native/elements/export`, `Event.pane == "zoom"` (the I2 PaneBus),
  `view.on(pane="zoom")`, [D151] linking (labels are just labels).

Tier-2 tests: `view.panes` order `["0", "zoom"]` for a single-surface parent
with one labeled inset; `pane("zoom").set_range` + capture; **inset window
survives `set_backend("pyqtgraph" ⇄ "matplotlib")`**; RangeEvent from the
inset carries `pane="zoom"`; `pane("zoom").elements == (child ids)`;
per-pane export writes the inset only.

## I4 — the static zoom indicator ([D154] v1)

In the parent's children loop, after rendering an inset with
`indicate=True`: read `surf = surface_of(inset.child)`; if **both**
`surf.x.lim` and `surf.y.lim` are declared, synthesize
`Rect(x0, y0, x1, y1, line_style="dashed")` (the existing wave-1 annotation
— data-space on the parent, lowers everywhere, zero new drawing code) and
render it through `_render_element` with the parent ctx; else warn-once
(`"indicate=True needs declared x/y lims on the inset until the live
indicator lands"`). The synthesized Rect gets no id in `natives` (chrome).

Tier-2: indicator artist present at the declared lims on pg + mpl; missing
lims → warning, no rect. **I4b (separate gate):** the live
`_InsetIndicator` controller — subscribe `RangeEvent(pane=<inset>)`, move
the rect natively (`_LinkController` file pattern in `core/_host.py`…
except this one is per-backend-handle; place with the raster controllers).
Not scheduled until the static version proves demand.

> **I4b shipped 2026-08-06:** `core/_indicator.py` `InsetIndicator`, one
> per indicating inset, subscribed on the handle bus and filtered by pane
> label; pg rewrites the QGraphicsPathItem path (parent-log-aware), mpl
> `set_xy`s the Polygon patch. The static lims gate is lifted — an
> undeclared window seeds from the inset's rendered range (pg `viewRange`
> delogified / mpl `get_xlim`), so the warn-skip is gone. Controllers ride
> the raster-controller dispose slots (`_qtviz_indicators`).

## I5 — webengine catch-up (independent; the risky one)

`_figure.build` learns a second axis pair per inset: `xaxis2/yaxis2` with
`domain` from `rect`, child traces bound via `xaxis: "x2"`; `_translate`
learns `xaxis2.range` relayout parsing (R1 log map per axis pair);
`_WebPane` grows one pane per inset (shadow ranges per axis pair). Replaces
the warn-skip. Own spike + go/no-go; nothing in I1–I4 depends on it.

## Cross-cutting obligations

- Freeze triple lands in I1 (the name), CHANGELOG entries per step.
- `docs/api.md`: `::: qtviz.Inset` in the Elements section + a line in the
  Panes section (I3).
- Gallery: extend `37_named_panes.py` (or a small `38_inset_zoom.py`) with a
  zoom inset + indicator once I4 lands; regenerate that screenshot only.
- No benchmarks: render-time only, no per-frame path touched (stated per
  cadence so the omission is a decision).
- Est. sizes: I1 **S–M**, I2 **M** (pg spike inside), I3 **S**, I4 **S**,
  I5 **M–L**.
