# Milestone M4 — Interaction (native events + linked axes/brushing)

> Focused plan for the next build milestone. Umbrella: `development-plan.md`
> (component map, invariants, verification tiers). Gate it serves: the
> roadmap **Phase 1 acceptance milestone** — a 3-panel dashboard (Scatter +
> Histogram + Curve), shared X axis, linked brushing, `Theme.dark()`, under
> 60 LOC, 100% pyqtgraph.
>
> References `discussion-items.md` as **[D#]**.

## 1. Goal

Make pyqtgraph plots actually *interactive*: native Qt events (range, pick,
select/brush, hover, tap) flow through the typed `EventBus` to `View.on(...)`
subscribers with the declared throttling, and multi-panel layouts share axes
via `link_x` / `link_y`. This is the capability that justifies the native
pivot — today the bus exists but nothing emits, and `LayoutOptions.link_x` is
parsed but not wired.

## 2. Starting point (what M0–M3 already give us)

- `EventBus` with per-type default throttling + `Disposable` subscriptions
  (`core/event.py`) — built, but no backend publishes to it.
- `RenderContext` carries `event_bus`; every renderer already receives it and
  the Element's `id`.
- pyqtgraph backend renders all 8 elements into `PlotItem`s; `View.on()`
  records subscriptions and rebinds them across rebuilds.
- `ViewState` capture/restore (ranges) works.

So M4 is **wiring**, not new architecture: translators from native signals to
typed events, plus axis linking, plus the gate example.

## 3. Components

### 3.1 New — `backends/pyqtgraph/_events.py`

Native → typed translators. One `wire_*` per primitive; each captures the
`source_id` and the `EventBus` and connects the relevant pyqtgraph signal.

```python
def wire_viewbox(plot, surface_id, bus):
    # ViewBox.sigRangeChanged(vb, ranges) → RangeEvent(surface_id, x, y)
    # Also drives TapEvent on a click in empty space (scene sigMouseClicked).

def wire_scatter(item, source_id, bus):
    # ScatterPlotItem.sigClicked(item, points[, ev]) → PickEvent(source_id, idx, x, y)
    # item.setData(hoverable=True); sigHovered(item, points) → HoverEvent(...)

def wire_brush(plot, elements, bus):
    # region/rubber-band select over the ViewBox → SelectEvent(surface_id,
    # indices, bounds). The indices are computed per element from its
    # snapshot x/y against the selected bounds.
```

`sigClicked`'s signature differs across pyqtgraph versions (`(item, points)`
vs `(item, points, ev)`); the wrapper accepts `*args` and reads positionally.

### 3.2 New — `backends/pyqtgraph/_axes.py`

```python
def link_axes(plots, *, link_x: bool, link_y: bool):
    base = plots[0].getViewBox()
    for p in plots[1:]:
        if link_x: p.getViewBox().setXLink(base)
        if link_y: p.getViewBox().setYLink(base)
```

Called from `render.py::_render_into` for a single-backend `Layout(grid)`
when `node.options.link_x/​link_y`. (Cross-backend linking stays out of scope
— that needs the LayoutHost, a later milestone.)

### 3.3 Modified — renderers + `RenderContext`

Each `render_*` calls the matching `wire_*` after building its item, passing
`element.id`. `RenderContext` gains a `surface_id: str` (the plot's id) so
range/select translators can stamp surface-level events (see §4 / [D8]).
`PgRenderHandle` wires `wire_viewbox` / `wire_brush` per plot at render time.

### 3.4 Modified — `core/event.py`

No API change; verify the `QTimer` throttle delivers correctly under a running
loop (it is exercised for the first time here). Add a test hook to flush
pending throttled emits deterministically (`EventBus._drain()` for tests).

### 3.5 New — `examples/dashboard_native.py`

The Phase 1 gate, in < 60 LOC: `Scatter + Histogram + Curve` in a grid with
`link_x=True`, a `Theme.dark()`, and a `view.on(SelectEvent, ...)` that
filters/highlights across panels. Runnable; backed by a smoke test.

## 4. Event mapping + source identity ([D8] applied)

| Native (pyqtgraph) | Typed event | `source_id` |
|--------------------|-------------|-------------|
| `ViewBox.sigRangeChanged` | `RangeEvent` | **surface** (plot id) |
| rubber-band / region select | `SelectEvent` | **surface** |
| `ScatterPlotItem.sigClicked` | `PickEvent` | **element** id |
| `ScatterPlotItem.sigHovered` | `HoverEvent` | **element** id |
| scene click on empty space | `TapEvent` | **surface** |

Per [D8] (accepted): axes-level events (range/select/tap) carry a *surface*
id; element-level events (pick/hover) carry the Element `id`. A "surface id"
is minted per `PlotItem` at render and exposed on the handle, so subscribers
can disambiguate panels. Document which events are surface vs element in
spec §2.10 as part of this milestone.

## 5. Build order

Each step ends green before the next starts.

1. **`_events.wire_viewbox` + RangeEvent** — the simplest signal; prove the
   native→typed→bus→`View.on` path end to end. *Verify:* drive
   `vb.sigRangeChanged` (or `vb.setRange`) → a throttled `RangeEvent` arrives.
2. **`wire_scatter` (pick + hover)** — element-id events. *Verify:* emit
   `sigClicked` programmatically → `PickEvent` with the right index.
3. **`_axes.link_axes` + render hookup** — `Layout([...], link_x=True)`.
   *Verify:* zoom panel A's X → panel B's X range tracks it.
4. **`wire_brush` + SelectEvent** — the hard one (§7). *Verify:* select a
   bounds rect → `SelectEvent` with the indices inside it.
5. **TapEvent** + surface-id plumbing.
6. **Gate example** `examples/dashboard_native.py` + smoke test.

## 6. Acceptance & benchmarks

New/activated tests (extend the existing suite, no new tiers):

- **Conformance (Tier-3) — add `test_declared_events_fire`**: for each backend,
  for each event its `Capabilities` declare supported, drive the native source
  and assert exactly that typed event is delivered; assert *undeclared* events
  never fire. (This is the §5.3 test sketched but not yet written.)
- **View (Tier-2)**: `test_range_event_on_zoom`, `test_pick_event_on_click`,
  `test_select_event_on_brush`, `test_linked_axes_share_range`,
  `test_throttle_coalesces_range_events`.
- **Gate**: `examples/dashboard_native.py` runs headless and emits a
  `SelectEvent` that updates the other panels.

Driving events in tests: prefer invoking the **native signal directly**
(`item.sigClicked.emit(...)`, `vb.setRange(...)`) over synthetic mouse events —
robust and coordinate-independent. `qtbot.waitSignal` / a throttle `_drain()`
makes throttled delivery deterministic.

## 7. Risks / discussion items

- **Brush-selection is the hard part.** pyqtgraph has no built-in
  "rubber-band → selected point indices". Options: (a) `ViewBox` in
  `RectMode` + read the rect on `sigRangeChanged`/mouse-release and test each
  element's points against the bounds; (b) a draggable `RectROI`/
  `LinearRegionItem` the user toggles. Recommend (a) for Phase 1 (no extra UI
  affordance), computing indices from each element's snapshot. **New item
  [D12]** — record the chosen brush mechanism and its toggle/UX.
- **[D8] source identity** — applied here; needs the spec §2.10 note + a
  surface-id on the handle.
- **Throttle under the event loop** — first real exercise of the `QTimer`
  trailing-edge path; verify no lost trailing emit and that `dispose()` stops
  timers (no leaks across rebuilds).
- **[D7] update coalescing** — rapid range/select bursts during reactive work
  (Phase 4) will stress this; out of scope now but the throttle is the seam.

## 8. Re-sequencing note (what comes after M4)

The umbrella plan had **M5 (mixed-backend host) → M6 (matplotlib)**. Reverse
them: `LayoutHost` / `CompositeRenderHandle` only become testable with a
*second* backend, so build **M6 (matplotlib) before M5**. Revised tail:

```
M4 Interaction → M6 matplotlib (the abstraction proof) → M5 mixed-backend host
```

M6 also unblocks the deferred vector-export path (svg/pdf via matplotlib),
which is why pyqtgraph declares png-only today.

## 9. Out of scope for M4

- Cross-backend / mixed-pane axis linking (needs LayoutHost — M5).
- Selection persistence in `ViewState` ([D2] ranges-first; selection later).
- Reactive re-aggregation on range change (Phase 4 / Datashader).
- Synthetic OS-level mouse-event testing (drive native signals instead).
