# Milestone — color & size encoding (toward the HoloViews adapter)

> Data-driven color and size: bind `color_by` / `size_by` to a column and the
> renderer maps it to per-point color/size with an automatic legend. The mapping
> is a single pure rule shared across backends (and, by design, with Datashader),
> so a column colors the same way however it's drawn. This is a prerequisite the
> HoloViews adapter needs ([D23], `capabilities-gaps.md`). References
> `discussion-items.md` as **[D#]**.

## 1. The shape

```
Scatter(df, x, y, color_by="z")
   resolve pipeline → channels() adds role "color" (and "size" for size_by)
   → EagerTabularRef has a "color" array
   render_scatter (per backend):
       map_colors(values, palette=theme.palette, continuous_palette=viridis)
            → (rgba: (N,4), Legend)
       → per-point brushes/colors + an auto legend / colorbar
```

Two decisions keep it a clean, reusable foundation:

1. **One pure mapping rule** (`core/encoding.py`, Qt-free). `map_colors(values)
   → (rgba, Legend)` decides categorical-vs-continuous by dtype, maps through a
   `Palette`, and returns a backend-agnostic `Legend` (categorical entries, or a
   continuous `vmin/vmax` + ramp). Both backends — and conceptually Datashader —
   consume the same rule, so encoding is defined once, not per renderer.
2. **The channel materializes through the existing pipeline.** `Scatter.channels()`
   adds a `"color"`/`"size"` role when `color_by`/`size_by` is bound, so the
   resolve pipeline (and its lazy/out-of-core path) produces the column with no
   special-casing. Datashader is unaffected: it rasterizes *before* channels
   resolve and aggregates `color_by` itself.

## 2. What this built

- **`core/encoding.py`** — `map_colors` + `Legend`. Categorical: `np.unique` →
  palette swatch per category. Continuous: a 256-entry palette LUT, normalized by
  `vmin/vmax`, NaN-safe; legend carries 5 ramp stops. Tier-1 tested.
- **`Scatter.channels()`** — materializes `color`/`size` roles when bound.
- **Native renderers** (both backends) — `render_scatter` applies the mapping to
  per-point brushes (pyqtgraph) / `c=` array (matplotlib) and per-point sizes;
  falls back to static `color`/`size` when unbound.
- **Legends** — auto-added when `color_by` is set: matplotlib uses native
  `ax.legend` (categorical) / `figure.colorbar` (continuous); pyqtgraph lists
  swatches in a `LegendItem`, continuous drawn as a 5-step colorbar
  (`backends/pyqtgraph/_legend.py`).
- Tests: encoding (Tier 1) + per-backend color/size/legend wiring (Tier 2);
  `examples/12_color_mapping.py`.

## 3. Deliberate limits (tracked in `capabilities-gaps.md`)

- **Scatter only** — `Curve`/`Bars` color encoding and per-series legends are
  follow-ups.
- **Datashader rasters carry no legend yet**, and the raster path still uses its
  own palette defaults rather than the shared `Palette` — aligning them (and a
  raster colorbar) is the next encoding step.
- **Legend is not yet a first-class element** — it's auto-attached by the
  renderer, not a composable node you can place/toggle. The HoloViews adapter will
  want it addressable; promote it then.
- Continuous defaults to `viridis`; a theme-supplied continuous palette is a gap.

## 4. Discussion items

- **[D23]** color encoding — a shared pure `map_colors`/`Legend` (not per-backend,
  not Datashader-only); `color_by`/`size_by` materialize as channels; legend
  auto-attached. Continuous default `viridis`; legend-as-element + raster legends
  deferred. ✅ accepted/applied.
