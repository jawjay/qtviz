# Changelog

All notable changes to qtviz are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — 0.3.0

First-class axes + legends (root cause R5; `design/milestone-0.3-firstclass.md`,
[D59]/[D60]). The two afterthoughts promoted to real models.

### Added

- **First-class axes ([D59]).** `qv.AxisSpec` (`label` / `scale` / `lim` /
  `invert`) on `OverlayOptions.x`/`.y` + `aspect`. `scale="log"` renders on
  **all three backends** — with every coordinate crossing the seam (events,
  brush bounds, capture/restore, backend switches) normalized to **data
  space**, never log space. `symlog` renders on matplotlib and warns→linear
  elsewhere (`Capabilities.scales` gating); non-positive values under log
  drop with a one-time `QtvizWarning`; rasters (Image/Heatmap/datashaded)
  under a non-linear scale warn and render linear. Declarative `lim` sets the
  initial range; a live pan/zoom (`ViewState`) wins across rebuilds.
- **Legend contract ([D60]).** A `label` field on the styling elements
  (Scatter/Curve/Bars/Histogram/ErrorBars/Spread) + `Element.legend_entry()`;
  an Overlay aggregates contributions into **one** legend, merged with any
  `color_by` color-mapping legend (no double legends — a `color_by` Scatter
  opts out of the contract). The previously-dead `OverlayOptions.legend` now
  works, joined by `legend_position` (`auto|right|top|none`); `legend=False`
  silences every legend path, including raster re-aggregation refreshes.
- **Legend parity ([D55]).** webengine finally draws legends (`showlegend`
  follows the surface; traces opt in per-label) and a true Plotly colorbar for
  continuous `color_by`; pyqtgraph's 5-stop stepped swatch is replaced by a
  true gradient `pg.ColorBarItem` (eq_hist density honestly keeps its
  endpoints-only key, [D48]).
- Docs drift guard: every `qtviz.__all__` name must appear in `docs/api.md`
  (tier-1 test, improvement-plan [D65]).

## [0.2.0] — 2026-06-18

Hardening pass from the post-0.1 weakness investigation (root causes R1–R6;
`design/weakness-root-causes.md`). No new chart types — the existing surface made
**honest**, plus a native escape valve.

### Fixed

- **Silent option drops are gone (§3.4 honor-or-warn, [D51]).** An option a backend
  doesn't support no longer vanishes silently — it warns once (`QtvizWarning`) and
  rendering proceeds. Newly *honored* (were dropped): `Scatter.marker` (all backends),
  `Scatter.alpha` and `Curve.line_style`/`alpha` (pyqtgraph), `Image.interpolation`
  (matplotlib). A backend-conformance test now guarantees every recommended option is
  honored-or-warned, so silent drops can't return.

### Changed

- **Honest capabilities ([D52]).** matplotlib and webengine no longer advertise
  `dimensions={2,3}` or `animation` — there is no 3-D renderer or animation API yet;
  both are corrected, and a conformance test guards against aspirational flags.

### Added

- **`View.native(element_id)` / `RenderHandle.native(element_id)`** — the escape
  valve ([D53]) to the live backend primitive (pyqtgraph `PlotItem`, matplotlib
  `Artist`/`Axes`, or the webengine figure host) for backend-native interaction the
  typed events don't expose: ROIs, crosshairs, region selectors, native signals.
  Non-portable by design; the live object is returned *through the handle*, never
  stored on the immutable Element, so the purity invariant holds. Rebuilds on
  `update()`. Composite (mixed-backend) handles fan out across panes.
- `qtviz.errors.QtvizWarning` — a filterable category for non-fatal degradation notices.

### Deprecated

- **`qtviz.Options`** — unused (per-element styling lives on the elements themselves);
  constructing it now warns (`DeprecationWarning`). Removed after 1.0.

## [0.1.0] — 2026-06-18

First public pre-release. One immutable `Element` API rendered across three
backends, a lazy-first data layer, and a big-data path — all 100% offline.

### Added

- **Core model** — immutable, value-hashed `Element` (Scatter, Curve, Bars,
  Histogram, Image, Heatmap, ErrorBars, Spread) plus `RawFigure` passthrough;
  `Overlay` (`*`) and `Layout` (`+`: grid / splitter / tabs / dock) composition;
  a typed event bus (`Range` / `Pick` / `Select` / `Hover` / `Tap`).
- **Backends** — pyqtgraph (native, default, OpenGL), matplotlib (vector export),
  and webengine (Plotly in a `QWebEngineView`, plus `RawFigure` hosting for
  Plotly / Bokeh / HoloViews). Registered, never imported by the core; runtime
  backend switching; mixed-backend layouts with one merged event stream.
- **Data layer** — container-agnostic, lazy-first accessors (column / `Expression` /
  callable / array) over dict / NumPy / pandas / Arrow (eager) and Dask / xarray /
  zarr (out-of-core, off the GUI thread); `tabular()` / `gridded()` shape overrides.
- **Encoding** — `color_by` / `size_by` with automatic legends and colorbars.
- **Datashader** — `Scatter` / `Curve` with `scale="datashader" | "auto"`: density,
  `color_by` mean, categorical blend; out-of-core, backend-agnostic, re-aggregating
  to the viewport on zoom. Hover a raster for the aggregated value
  (`HoverEvent.value`). Datashaded rasters now carry a **legend / colorbar**, take
  their **colors from the View's `Theme`** (matching a native `color_by`), and expose
  a wider **aggregation surface** via `Scatter.agg`
  (`count`/`sum`/`mean`/`max`/`min`/`std`/`any`/`by`) — built on an aggregate/shade
  split ([D47]–[D50]). Density keeps an honest endpoints-only key under `eq_hist`;
  value aggregations show a truthful linear colorbar.
- **Reactive** — S-style `signal` / `derived` / `effect` / `batch`;
  `View(Signal[Node])` re-renders on change; crossfilter / linked brushing without
  manual wiring.
- **HoloViews / hvplot adapter** — `from_holoviews(obj)` translates a HoloViews tree
  to native Elements (`RawFigure` fallback for the long tail); `DynamicMap` →
  `Signal[Node]` one-way re-render (`from_holoviews_dmap`); `from_hvplot(df, kind, …)`
  one-liner.
- **Offline guarantee** — no network at render time; the webengine backend bundles
  its JavaScript from the installed packages, never a CDN.
- **Export** — PNG (pyqtgraph), PNG / SVG / PDF (matplotlib), PNG (webengine).
- **Validation contract** — bad constructor input (out-of-range opacity,
  mutually-exclusive channel pairs, unknown column) raises
  `qtviz.errors.ValidationError`, which subclasses **both** `QtvizError` and the
  stdlib `ValueError`; `except QtvizError` now catches every deliberate rejection,
  including construction errors, while `except ValueError` keeps working. Mutable
  setters validate eagerly: `set_default_backend` rejects an unregistered name,
  and `set_raster_threshold` / `set_raster_size` reject non-positive values. Every
  `data=` parameter is annotated `DataLike`.
- `qtviz.__version__`.

### Notes

- `qtwebplot` was renamed to qtviz; `import qtwebplot` keeps working through a
  deprecation shim (redirects to `qtviz.backends.webengine`) for two releases.
- Not yet published to PyPI; the public API may still change before 1.0.
