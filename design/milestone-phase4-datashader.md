# Milestone — Phase 4: Datashader (big-data rendering)

> Aggregate millions–billions of points into a screen-resolution raster, so a
> scatter that would overplot (or OOM the native backends) becomes a density
> image. Companion to `milestone-data-core.md` (the lazy data layer this builds
> on) and the roadmap. References `discussion-items.md` as **[D#]**.

## 1. The shape of the foundation

Two decisions make this a *flexible* foundation rather than a backend feature:

1. **Aggregation is backend-agnostic; it lives in the pipeline, not a backend.**
   The rasterizer produces an RGBA array + bounds, and the routing wraps that as
   a plain `Image`. So *every* backend renders a datashaded scatter for free
   (pyqtgraph and matplotlib already do), and a future backend gets it with no
   extra work. A huge `Scatter` is rewritten to an `Image` by `resolve_node`
   ([D18]).

2. **It aggregates the lazy source directly — out-of-core.** `channel_frame`
   assigns the channel accessors as columns onto a **dask** frame and hands that
   (still lazy) to datashader, which aggregates partition-by-partition. Only the
   small raster is materialized; the points never all land in memory. Eager
   sources fall back to a pandas frame.

```
Scatter(huge_data, scale="datashader" | "auto")          # user
        │  resolve_node (off the GUI thread, Phase-2 async path)
        ▼
   channel_frame(data, {x, y})   →  lazy dask/pandas frame with x,y columns
        │  datashader Canvas.points + shade   (out-of-core)
        ▼
   Image(rgba, bounds)           →  any backend renders it
```

## 2. What step 4a built

- **`ext/datashader.py`** — `rasterize_points` (Canvas.points → `count` agg →
  `tf.shade` → RGBA + bounds) and `channel_frame` (lazy frame from accessors).
  Accessor-aware: string / Expression / callable x,y all work.
- **Pipeline routing** — `_needs_rasterize` (scale `"datashader"` always; `"auto"`
  above `set_raster_threshold` or when size is unknown/lazy), `resolve_node`
  rewrites `Scatter → Image` off-thread, `node_is_lazy` returns True so it uses
  the async View path. `set_raster_threshold` / `set_raster_size` config.
- **RGBA `Image` rendering** — both backends' Image renderers handle a 3-D RGBA
  array (skip the float/colormap path) so the shaded raster displays correctly.
- Tests: rasterizer correctness (density concentrates), dask stays lazy
  (out-of-core), pipeline routing for every scale, async render on both backends.

`datashader` added as the `[datashader]` optional extra.

## 3. Next stage (4b) — viewport-driven re-aggregation ([D21])

Static rasterization shows the whole dataset at the initial extent; zooming in
just scales the image (blurry). The payoff of datashader is **re-aggregating to
the visible viewport at the widget's pixel size as you pan/zoom**, so the image
sharpens. That loop is the next stage and is *backend-coupled* (it reads the
viewport + pixel size and updates the image primitive), so it needs a thin
per-backend seam:

```python
class RasterTarget(Protocol):           # one tiny impl per backend
    def viewport(self) -> tuple | None         # current (x_range, y_range)
    def pixel_size(self) -> tuple[int, int]     # widget px
    def set_raster(self, rgba, bounds) -> None  # update the image in place
    def on_viewport_change(self, cb) -> Disposable

class RasterController:                  # backend-agnostic, owns the loop
    # on viewport change (debounced) → rasterize_points(frame, …, x_range, y_range,
    #   width, height) off-thread → target.set_raster(...). build-id drops stale.
```

The aggregation primitive (`rasterize_points`) and the async/debounce machinery
are reused; only `RasterTarget` is new per backend. This keeps 4b small.

## 4. Discussion items

- **[D18]** rasterization site — backend-agnostic pipeline transform (Scatter →
  Image) ✅.
- **[D19]** auto-route policy — global `set_raster_threshold`; lazy/unknown-size
  sources route too (force `scale="native"` to opt out) ✅.
- **[D20]** output form — RGBA via `tf.shade` (best out-of-box visual, reuses
  RGBA Image rendering) for 4a; raw-aggregate + theme colormap (interactive
  colormaps, theme integration) is a future enhancement ✅/open.
- **[D21]** dynamic viewport re-aggregation seam — `RasterController` +
  `RasterTarget` (open, stage 4b).
- **[D22]** coverage — points (`Scatter`) now; lines/areas (`canvas.line`) and
  categorical color (`count_cat` via `color_by`) are follow-ups (open).
