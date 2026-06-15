# Milestone — Raster reverse-lookup (hover/inspect on a datashaded view)

> The datashader path turns a huge `Scatter`/`Curve` into a density `Image`
> ([D18–D22]), but the result is a bare raster: hover/pick resolve through points,
> and a raster has no per-point identity, so a datashaded view is non-interactive
> for inspection. This milestone adds **pixel → aggregated-value lookup**: hovering
> a datashaded plot reports the `count`/`mean` under the cursor. It is the first
> step toward selection/linked-brushing on rasters (`capabilities-gaps.md` §2
> *Interaction*). New decision **[D46]**. Companion to
> `milestone-phase4-datashader.md` (the agg + 4b loop this extends) and
> `core/event.py` (the event model).
>
> **Status: ✅ implemented** as specced below. `HoverEvent.value`, `RasterResult`/
> `RasterAggregate` (`ext/datashader.py`), the controller `on_aggregate` freshness
> hook (`core/raster.py`), and per-backend hover wiring (`pyqtgraph/_raster.py`,
> `matplotlib/_raster.py`) all landed; tests in `tests/qtviz/test_raster_inspect.py`.
> **Offscreen-test note:** a datashaded view's hover handler connects to the
> scene-global mouse signal; pytest-qt's inter-test `_process_events` can fire a stray
> move into a not-yet-disposed view, and with *both* native backends' views live this
> segfaults offscreen (the [D45]/de-flake family). The Tier-2 hover tests therefore
> call `view.handle.dispose()` at the end to sever the connection deterministically —
> the same severing a real app gets from the normal View lifecycle.

## 1. The gap

`ext/datashader.py::_aggregate_and_shade` computes a datashader aggregate `agg`
(an xarray `DataArray` of `count`/`mean` per pixel, with data-space coords) and
then `tf.shade`s it to RGBA. It returns only `(rgba, bounds)` — **the aggregate is
discarded.** Without it, there is nothing to look a pixel up *in*. Reverse-lookup
is therefore mostly "retain the aggregate and thread it to the hover handler,"
plus a small amount of per-backend mouse-move wiring.

Two paths produce/refresh a raster, and the aggregate must travel through **both**
or hover values go stale after a zoom:
- **static** — `data/pipeline.py::_rasterize` (initial render at `_RASTER_SIZE`).
- **dynamic** — `core/raster.py::RasterController` re-aggregates to the viewport at
  widget resolution on pan/zoom (4b), calling `target.set_raster(rgba, bounds)`.

## 2. Design

### 2.1 A pure value object: `RasterAggregate` (Qt-free, Tier-1 testable)

Lives in `ext/datashader.py` (pure numpy; datashader still imported lazily only
for the aggregation). Carries the per-pixel values + the data-space extent and
does the pixel mapping:

```python
@dataclass(frozen=True)
class RasterAggregate:
    values: np.ndarray   # (rows=y, cols=x) scalar agg; NaN where the pixel is empty
    bounds: tuple        # (xmin, ymin, xmax, ymax); row 0 == ymin (origin lower-left)
    kind: str            # "count" | "mean" | "category" — what the value *means*

    def value_at(self, x: float, y: float) -> float | None:
        """Data coords → pixel → value. None outside bounds or on an empty pixel."""
```

`value_at` maps `x→col`, `y→row` by linear scaling into `bounds`, clamps to the
last cell on the upper edge, and returns `None` for out-of-bounds or empty
(NaN / count 0) pixels.

### 2.2 Retain + thread the aggregate: `RasterResult`

The rasterizers return a richer result instead of a bare tuple (internal API; all
~3 call sites updated, no compat shim per project policy):

```python
@dataclass(frozen=True)
class RasterResult:
    rgba: np.ndarray
    bounds: tuple
    aggregate: RasterAggregate
```

- `_aggregate_and_shade` keeps the `agg` it already computes and builds the
  `RasterAggregate` from `agg.values` + `bounds` (+ `kind`). For categorical
  `by(count)` (3-D agg) the first cut collapses to **total count per pixel**
  (`agg.sum(over categories)`), `kind="category"`; the per-category breakdown is a
  follow-up (§5).
- `rasterize_points` / `rasterize_line` / `rasterize_element` return `RasterResult`.
- **static path:** `_rasterize` attaches `result.aggregate` to the produced `Image`
  as a private `_raster_aggregate` (alongside the existing `_raster_source`; private
  → excluded from value identity).
- **dynamic path:** `RasterController` consumes `RasterResult` and, after
  `target.set_raster(rgba, bounds)`, invokes an optional injected
  `on_aggregate(aggregate)` callback (GUI thread) so the hover handler always reads
  the *current* aggregate. `RasterTarget` is **unchanged** — the freshness hook is a
  controller callback, not a new target method (keeps the per-backend seam minimal).

### 2.3 Event model: extend `HoverEvent` with `value` ([D46])

A raster hover has no point identity but does have a value. The general,
composable extension is one optional field on the existing event rather than a new
event type:

```python
@dataclass(frozen=True)
class HoverEvent(Event):
    point_index: int | None
    x: float
    y: float
    value: float | None = None      # NEW: aggregated value under the cursor (rasters)
```

Native `Scatter` hover is unchanged (`value` defaults to `None`, it already carries
`point_index`). A raster hover emits `HoverEvent(source_id=<scatter id>,
point_index=None, x, y, value=<agg or None>)`. `source_id` is the rasterized
`Image`'s `id`, which `_rasterize` already sets to the source element's id — so
events line up with the originating Scatter.

### 2.4 Per-backend hover wiring (the only new Qt code)

A shared mutable holder (`{aggregate}`) is parked on the surface next to the
controller; the controller's `on_aggregate` updates it, the hover handler reads it.
Delivery rides the existing `HoverEvent` throttle (33 ms default) and `value_at` is
O(1), so per-move cost is negligible.

- **pyqtgraph** (`backends/pyqtgraph/_events.py` + `_raster.py`): on
  `vb.scene().sigMouseMoved`, map scene→view via `vb.mapSceneToView`, and if inside
  the image bounds emit a throttled `HoverEvent` with `holder.aggregate.value_at`.
- **matplotlib** (`backends/matplotlib/_events.py`): on canvas `motion_notify_event`
  with `event.inaxes is ax`, use `event.xdata/ydata` and emit the same.

Wired only for an `Image` that has `_raster_aggregate` (i.e. came from datashading);
a plain `Image` is unaffected.

### 2.5 Flow

```
rasterize_element(scatter) ─→ RasterResult(rgba, bounds, RasterAggregate)
   static: _rasterize → Image(rgba, bounds){_raster_source, _raster_aggregate}
   render_image → seed holder.aggregate; wire RasterController(on_aggregate=holder.update)
                → wire hover(vb/canvas, source_id, bus, holder)
   user moves cursor → value_at(x,y) → HoverEvent(point_index=None, x, y, value)
   user zooms → controller re-aggregates → set_raster + holder.update(new aggregate)
                → subsequent hovers read the fresh values
```

## 3. Decisions — [D46]

- **Event shape:** extend `HoverEvent` with `value: float | None = None` (general,
  back-compatible) rather than a new `InspectEvent`. *Recommend; confirm at review.*
- **Aggregate freshness:** controller `on_aggregate` callback + shared holder, leaving
  `RasterTarget` unchanged. *Recommend.*
- **Categorical:** first cut returns total count per pixel (`kind="category"`);
  per-category breakdown deferred. *Recommend.*
- **Auto vs opt-in:** automatic for datashaded Images (throttled, O(1)); no API knob.
  *Recommend.*

## 4. Verification (write before implementing)

- **Tier 1 — `RasterAggregate.value_at` (pure, no Qt, no datashader).** Build an
  aggregate from a known array + bounds; assert corners, center, the upper-edge
  clamp, out-of-bounds → `None`, empty pixel (NaN/0) → `None`. Most coverage here.
- **Tier 1 — retention.** `rasterize_element(scatter)` returns a `RasterResult`
  whose `aggregate.values` shape matches `(height, width)` and whose dense region
  has the higher count (mirrors the existing "density concentrates" test).
- **Tier 2 — hover emits value (both native backends).** Render a datashaded
  Scatter; synthesize a mouse-move at a dense data coord; assert a `HoverEvent`
  with `point_index is None` and `value` matching `aggregate.value_at`. A move
  outside → `value is None`.
- **Tier 2 — freshness after re-aggregation.** After a viewport change drives the
  controller (reuse the 4b zoom test harness), the holder's aggregate is the new
  one and a hover reflects the re-aggregated value.
- **Tier 4 — bench.** Per-hover `value_at` cost is microseconds; assert a soft
  ceiling so it never creeps into the event path.
- **`HoverEvent.value` back-compat:** existing native-scatter hover tests still pass
  unchanged (value defaults to None).

## 5. Out of scope (track in `capabilities-gaps.md` §2 Interaction)

- **Selection / brush on a raster** (pixels/region → source rows or a data-space
  predicate) — the next interaction step; this milestone is hover/inspect only.
- **Per-category value** for categorical rasters (return the category breakdown, not
  just total count).
- **webengine raster hover** — native backends first; webengine RawFigure has its own
  hover.
- **Curve/line inspect semantics** beyond line-density count (no per-series identity).

## 6. Build order (TDD)

1. Tier-1 tests for `RasterAggregate.value_at` + `RasterResult` retention (red).
2. `RasterAggregate`/`RasterResult` in `ext/datashader.py`; `_aggregate_and_shade`
   keeps the agg; rasterizers return `RasterResult`; update `_rasterize` + the 4b
   controller contract + their tests; green.
3. `HoverEvent.value` field (+ confirm native tests unaffected).
4. Controller `on_aggregate` callback; per-backend holder + hover wiring; Tier-2
   tests on both backends; freshness test.
5. Example: hover-to-inspect on a 1M-point datashaded scatter (prints value).
6. Bench; full offscreen suite 3× green.
