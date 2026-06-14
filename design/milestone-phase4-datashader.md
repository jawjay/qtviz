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

## 3. Stage 4b — viewport-driven re-aggregation ([D21]) ✅

Static rasterization shows the whole dataset at the initial extent; zooming in
just scales the image (blurry). The payoff of datashader is **re-aggregating to
the visible viewport at the widget's pixel size as you pan/zoom**, so the image
sharpens. That loop is *backend-coupled* (it reads the viewport + pixel size and
updates the image primitive), so it splits into a backend-agnostic controller and
a thin per-backend seam:

```python
class RasterTarget(Protocol):           # one tiny impl per backend
    def viewport(self) -> Viewport | None       # current ((x0,x1),(y0,y1))
    def pixel_size(self) -> tuple[int, int]     # widget px
    def set_raster(self, rgba, bounds) -> None  # update the image in place
    def connect_viewport(self, cb) -> Disposable

class RasterController(QObject):         # core/raster.py — backend-agnostic, owns the loop
    # on viewport change (debounced) → rasterize(source, x_range, y_range, width,
    #   height) on a worker pool → target.set_raster(...). A monotonic build-id
    #   drops stale results so a fast pan never paints an out-of-date raster.
```

**What 4b built**

- **`core/raster.py`** — `RasterTarget` protocol + `RasterController`. The
  controller debounces viewport changes (QTimer), re-aggregates off the GUI
  thread (shared pool), and drops stale results by build-id. `rasterize` is
  *injected*, so core carries no datashader dependency.
- **The source travels with the raster.** `_rasterize` parks the original (lazy)
  Scatter on the produced `Image` as a private `_raster_source`, so a backend can
  re-aggregate it. It's private → excluded from value identity (Image hashing /
  round-trip unchanged).
- **Per-backend targets** — `pyqtgraph/_raster.py` (`PgRasterTarget`: ViewBox
  range + geometry px → `ImageItem.setImage/setRect`) and `matplotlib/_raster.py`
  (`MplRasterTarget`: axes lims + window-extent px → `AxesImage.set_data/set_extent`,
  with a feedback guard since `set_extent` can mutate lims). Each backend's
  `render_image` wires a controller when `_raster_source` is present and parks it
  on the surface so the `RenderHandle` disposes it on teardown/update.
- Tests: controller contract (renders at widget resolution, re-aggregates on
  change, debounces a burst, drops stale, disposes cleanly) + end-to-end zoom
  re-aggregation on **both** backends (raster extent shrinks to the zoom window).

Out-of-core is preserved: a dask source stays lazy, so each viewport pass
aggregates only the visible window's partitions. The aggregation primitive
(`rasterize_points`) is reused unchanged; only `RasterTarget` is new per backend.

## 4. Discussion items

- **[D18]** rasterization site — backend-agnostic pipeline transform (Scatter →
  Image) ✅.
- **[D19]** auto-route policy — global `set_raster_threshold`; lazy/unknown-size
  sources route too (force `scale="native"` to opt out) ✅.
- **[D20]** output form — RGBA via `tf.shade` (best out-of-box visual, reuses
  RGBA Image rendering) for 4a; raw-aggregate + theme colormap (interactive
  colormaps, theme integration) is a future enhancement ✅/open.
- **[D21]** dynamic viewport re-aggregation seam — `RasterController` +
  `RasterTarget`, wired on pyqtgraph + matplotlib ✅.
- **[D22]** coverage — points (`Scatter`) now; lines/areas (`canvas.line`) and
  categorical color (`count_cat` via `color_by`) are follow-ups (open).
