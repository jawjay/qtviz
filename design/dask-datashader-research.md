# Dask & Datashader — research and positioning

> **Conclusion up front.** Datashader already solves "render a billion
> points" by server-side rasterization, and Dask owns the
> distributed-Python-data space. We should **integrate them, not compete
> with them.** Our differentiation is desktop-native, per-point GPU
> interaction at the 10M–100M scale, single-machine analytical workflows
> (DuckDB + Arrow), and a file-based project model — none of which they
> provide. The Studio's value proposition gets *sharper*, not weaker,
> after this analysis.

## 1. What each tool actually is

### 1.1 Dask

**One-line.** A parallel/distributed computing library for Python.

**What it provides.**

- `dask.dataframe` — a parallel pandas-like DataFrame. Lazy. Operations
  build a task graph; `.compute()` materializes.
- `dask.array` — parallel NumPy arrays for out-of-core / multi-machine.
- `dask.delayed` — wrap any Python function for lazy graph execution.
- `dask.distributed` — the cluster scheduler. Runs the same task graphs
  across processes, threads, or remote workers.
- A live dashboard at `localhost:8787` showing the task graph, memory,
  CPU, network — genuinely well-designed observability.
- `dask-expr` (2024+) — a query optimizer that rewrites DataFrame ops
  similar to a SQL planner.

**Modern direction.** Dask DataFrame is moving to Arrow-backed storage
under the hood (replacing pandas as the per-partition format). The
`dask-expr` engine pushes filters and projections down through the graph
the same way DuckDB or Spark would. The trajectory is "looks like a SQL
query planner, walks like a DataFrame."

**What it's great at.**

- Data too big for one machine's RAM.
- Multi-machine clusters.
- Workloads that genuinely parallelize (embarrassingly parallel batch
  jobs, ETL pipelines).
- A bridge from pandas code to scale without total rewrites.

**What it's not great at.**

- Single-machine, in-memory analytics — its scheduler overhead loses to
  DuckDB / Polars / even pandas for typical OLAP queries.
- Sub-second interactive workloads — task graphs and worker dispatch add
  10s–100s of ms per operation.
- Anything where the data fits in RAM and the query is simple.

### 1.2 Datashader

**One-line.** Server-side rasterization for huge datasets — turn a billion
points into a colored image, then display the image.

**The core idea.** At a typical screen size (say 1200×800), there are ~1M
pixels. A scatter of 1B points means each pixel covers 1000 points on
average. Most of those points overlap; rendering them individually is
both impossible (GPU memory, client bandwidth) and pointless (you can't
see them). So:

1. Aggregate points into a 2D pixel grid (count / mean / categorical) on
   the server side, in parallel.
2. Apply a colormap to the grid to produce an RGBA image.
3. Send the small image (~1–4 MB) to the client.
4. On zoom/pan, re-aggregate and re-send.

The aggregation step is Numba-accelerated and parallelizes well over Dask
partitions. Recent versions add GPU aggregation via `cuDF` for the
truly enormous cases.

**Ecosystem placement.** Part of HoloViz, alongside HoloViews, Panel, and
hvPlot. Standard usage: `holoviews.operation.datashader.datashade(scatter)`
returns an HoloViews element backed by Datashader; HoloViews + Bokeh
handle the rest (zoom triggers re-aggregation).

**What it's great at.**

- Truly arbitrary data scale. Billion-point scatters are routine.
- Density visualization — heatmaps, kdes, hexbins, gridded statistics.
- Integration with Dask for parallel aggregation.
- Categorical aggregation (one channel per category, blended in colorspace).
- Geo-spatial via `spatialpandas`.

**What it's not great at.**

- Per-point interaction. You're looking at pixels, not points. "Tell me
  which point is at this pixel" is fuzzy at best — you can get *a* point,
  but the visual conveys "many points here," not "this point here."
- Sub-frame zoom/pan responsiveness. Every viewport change triggers a
  re-aggregation roundtrip (Python → render → send → display). On a fast
  laptop this is 50–500ms; not instant.
- Smooth animations / continuous panning. The re-render cadence is
  serial; you'll see steps.
- Anything where the data already fits comfortably in GPU memory — you
  pay the rasterization tax for no benefit.

### 1.3 Panel (a close cousin worth covering)

**One-line.** Browser-served dashboarding for Python, like Streamlit /
Dash but with deeper HoloViz integration.

**Programming model.** Reactive via the `param` library — declare
parameters with types and dependencies; UI rebuilds when parameters
change. Mature, well-thought-out.

**Deployment.** Bokeh server, Tornado-based. Can also export static HTML
for some cases. There is a "Panel desktop" via PyInstaller, but it's a
Chromium frame around the same browser-served app — not a real native
integration.

**Why it matters.** Panel is the closest existing thing to "let me build
a multi-view linked dashboard in Python." But it's web-served by design;
state lives in a Tornado process; deployment means setting up a server.

## 2. The typical Python "huge data viz" stack today

For someone with a 100M-row Parquet file who wants an interactive scatter
plot, the canonical stack in 2025 is:

```
Parquet
  ↓  (read into a Dask DataFrame, partitioned by date or similar)
Dask DataFrame
  ↓  (datashade() — Datashader rasterizes each partition, combines)
Datashader Image
  ↓  (HoloViews wraps it; Bokeh renders it; Panel hosts it)
Browser dashboard
```

This works. It is mature. It is widely used. People have built real
products on it.

**It's also the path of least resistance for our notional users — so we
need to be honest about what we'd offer that's better, not just
different.**

## 3. Where we'd overlap with Dask + Datashader

Five overlap surfaces:

1. **"Visualize huge data."** Both stacks aim at this. They take
   different routes (server-rasterize vs GPU-render).
2. **Reactive coordination.** Panel's Param-based reactive model and our
   planned Signal/derived layer cover similar ground.
3. **Dashboarding.** Panel ships dashboards in browsers; our Studio
   ships them in a desktop app.
4. **Lazy compute graphs.** Dask's task graphs and DuckDB's query plans
   solve similar problems for similar workloads.
5. **Multi-backend abstraction.** HoloViews already abstracts Plotly /
   Bokeh / Matplotlib; we abstract Plotly / Bokeh / deck.gl / arbitrary
   JS. Same pattern, different backends.

## 4. Where we'd actually differ

Six concrete differences. Each is a real positioning lever.

### 4.1 Desktop-native vs browser-served

This is the biggest single differentiator. **No existing high-quality
Python visualization tool runs as a real native desktop application.**

- Panel / Streamlit / Dash / Voilà: all browser-served. Even "Panel
  desktop" is Chromium-wrapped.
- ParaView: native desktop, but scientific mesh data only and the UX is
  notoriously rough.
- PyQtGraph: native Qt, but limited to Qt-native rendering — no modern
  web vis tech, no deck.gl, no plotly.

For the Qt app developer who wants to embed a modern interactive
visualization, **we are currently the only option.** That's not a small
niche — every Qt-based scientific tool, finance terminal, EDA app, and
engineering desktop suite has this exact requirement.

For the analyst who wants a Tableau-class local-only tool: Tableau is
proprietary and expensive; Power BI is Windows-only and Microsoft-centric;
nothing else exists. The Studio fills that gap.

### 4.2 Per-point GPU interaction vs server-side rasterization

Datashader sends an image. We send the data and let the GPU render it.
The tradeoffs are real and material:

| Concern                          | Datashader                              | Our plan (deck.gl)                      |
|----------------------------------|-----------------------------------------|-----------------------------------------|
| Max plottable data points        | Effectively unlimited (Dask-bound)      | 10M–100M depending on GPU               |
| Pan / zoom responsiveness        | 50–500ms per viewport change            | Single-frame (GPU transform)            |
| Per-point picking                | Pixel approximation                     | Exact, by point ID                      |
| Brush selection of specific rows | Approximate (pixel bbox)                | Exact (point IDs in selection)          |
| Visual: density patterns         | Excellent (this is the whole point)     | Decent (with alpha; degrades >10M)      |
| Visual: individual outliers      | Lost (single points are sub-pixel)      | Preserved                                |
| Wire bandwidth                   | Tiny (KB image)                         | Large (MB data, but binary-compressed)  |
| Initial cold load                | Fast (small image)                      | Slower (data transfer dominates)        |
| Power use on idle interaction    | Low                                     | GPU active                              |

These are not "one is better" — they're different products. Datashader
wins for "I have a billion log records and want to see where the
anomalies cluster." We win for "I have 50M tick events and want to
brush-select 200 of them to investigate."

**The honest read: ship both. Datashader is a backend option for "too
big for the GPU." deck.gl backends handle "fits in GPU memory and I want
interactivity."** The Studio picks per-dataset and tells the user which
mode it's in.

### 4.3 DuckDB vs Dask for analytical workloads

For *single-machine* analytical workloads (filter, group-by, join,
window), DuckDB is significantly faster than Dask. Independent benchmarks
(ClickBench, H2O.ai db-benchmark) consistently show DuckDB beating Dask
on single-machine TPC-H by 3–10×. DuckDB's strengths:

- Vectorized execution.
- Native Arrow zero-copy.
- Smart query optimizer (filter pushdown, predicate folding).
- Out-of-core via memory-mapped Parquet without explicit partitioning.
- Single-process — no scheduler overhead.

Dask still wins for:
- Multi-machine clusters.
- Workloads where the entire pipeline is a Python function (not SQL).
- ETL where you want pandas semantics and graph-based parallelism.

The Studio is a single-machine desktop app. DuckDB is the right choice
for our compute layer. Dask becomes a *data source* (read a Dask
DataFrame in, materialize a partition / sample / aggregate via DuckDB).

### 4.4 File-based projects vs deployed dashboards

Panel deploys as a service. The artifact is a Tornado app, a URL, a
container. Sharing means sharing a server.

The Studio's artifact is a `.qwpx` file — a self-contained project the
user opens, edits, saves, emails, version-controls. Like a `.tableau`
file but plain text and inspectable.

This matters for desktop users who:
- Don't want to deploy a server.
- Want to email a dashboard to a colleague.
- Want to version-control their analysis.
- Want their data to never leave the laptop.

### 4.5 Multi-modal first-class

Datashader does rasters. HoloViews adds charts. Panel adds widgets. They
don't natively cover 3D scenes (three.js), large geospatial (deck.gl
TileLayer), network graphs (Sigma.js), code editors (Monaco), or design
surfaces.

Our bridge primitives are agnostic. Adding a new backend means adding
event wiring and verbs, not changing the runtime. Multi-modal is *the*
direction Moonshot B opens — and a Studio that can put a 3D scene next
to a deck.gl scatter next to a Monaco SQL editor is something nobody is
shipping.

### 4.6 Integration into existing Qt apps

The library's first use case isn't the Studio — it's the developer
building a Qt scientific / finance / engineering app who wants to embed
a modern interactive plot. Datashader, Panel, and friends can't do this
cleanly because they assume a browser host. We're built for embedding
from day one.

## 5. The opportunity to *use* Dask + Datashader

The smartest move isn't competing — it's adopting.

### 5.1 `qtwebplot.ext.datashader` backend

A backend that wraps Datashader's aggregation pipeline:

```python
from qtwebplot.ext.datashader import DatashaderBackend
import datashader as ds

backend = DatashaderBackend(
    source=ddf,                          # Dask DataFrame
    x="lon", y="lat",
    aggregator=ds.count(),
    width=1200, height=800,
)
view = PlotView(backend)
```

We get billion-row capability for free. The bridge transports the
rasterized image; deck.gl draws the result as a textured layer. Pan/zoom
triggers Python-side re-aggregation via the existing command channel.

Effort: ~300 LOC. We benefit from a decade of Datashader work without
reimplementing it.

### 5.2 `qtwebplot.data.DaskSource`

A `DataSource` adapter for Dask DataFrames. Behind the scenes, materializes
relevant partitions on demand (DuckDB can query Dask DataFrames via
`duckdb.from_df(...)`). The user writes a Dask DataFrame; we figure out
when to compute and when to defer.

This makes Dask users first-class without forcing them onto our stack.

### 5.3 Studio "Datashader mode" toggle

In the Studio, a per-view toggle: "GPU points (max 50M)" vs "Datashader
raster (any size)." The Studio inspects the data size and recommends the
right one. The user gets the right tradeoff transparently.

## 6. Refined positioning statement

After this analysis, the Studio's positioning crystallizes to:

> **A desktop-native, Python-extensible data exploration application.
> Modern web visualization tech (deck.gl, three.js, Plotly, Bokeh) lives
> inside a real Qt app — no browser, no server, no deployment. GPU
> rendering for million-scale per-point interaction; Datashader
> integration for billion-scale density. DuckDB + Arrow for analytical
> queries. File-based projects you can email and version-control.**

What we are explicitly **not**:

- Not Tableau replacement for the casual analyst. (Different UX
  philosophy; we're more code-extensible, less point-and-click.)
- Not a competitor to Datashader. (We integrate them; they do
  rasterization better than we ever will.)
- Not a Panel/Streamlit/Dash replacement. (Different deployment story —
  we're desktop-native, not web-served.)
- Not a Dask competitor. (Dask owns distributed compute; we use it
  selectively as a source / batch tool.)
- Not a Jupyter replacement. (Different surface — they're notebooks,
  we're an app.)

What we *uniquely* are:

- The Qt-native modern visualization library.
- The desktop-native answer to "I want Tableau-class interaction with
  full Python power and 100M-row scale."
- The integration layer that lets a single project use deck.gl, Plotly,
  Datashader, and Bokeh in one consistent UI.
- The file-based, no-server, no-deploy alternative for desktop users
  who want to *own* their dashboards instead of host them.

## 7. Impact on the Moonshot C+D plan

The original plan stands, with these adjustments:

### Adjusted phases

**Phase 1 — Arrow + DuckDB + Dask data sources (was: Arrow + DuckDB)**

Add `DaskSource` as a built-in `DataSource` alongside the Arrow / Parquet
ones. Dask users shouldn't have to convert to use us.

**Phase 3 — GPU backend `ScatterGL` (unchanged scope)**

Position explicitly as "for data that fits in GPU memory." Don't oversell.

**New Phase 3.5 — Datashader integration (1 month)**

`qtwebplot.ext.datashader` backend. Image-based pan/zoom via standard
deck.gl tile semantics. Brush selection returns approximate point IDs
through the existing bridge. ~300 LOC.

This adds a month to the timeline but fills the "billions of points"
gap immediately and removes the awkward "GPU runs out of memory, now
what?" failure mode.

**Phase 5 — Studio shell, expanded**

The "data source" panel surfaces Dask DataFrames and Datashader-backed
views as first-class options. The Studio detects data size and
recommends a backend.

**Phases 6–8 — substantially unchanged.**

### Total timeline impact

Adds ~1 month (Phase 3.5). New total: ~15 months full-time, ~30+ side-
project. The Datashader integration is small but high-leverage — it lets
us truthfully claim "scales to your data, whatever size."

## 8. What this means for the deck.gl spike

The Phase 0 spike was going to test "can deck.gl handle 100M points at
30 FPS." With Datashader as a fallback, the spike's risk profile
changes:

- If deck.gl handles 100M: great, that's the GPU ceiling for us.
- If deck.gl tops out at 30M: fine, that's still huge and Datashader
  covers the rest.
- If deck.gl can't even do 10M: bad news, but Datashader still saves
  the product positioning.

The spike is still worth running, but it's no longer a make-or-break
gate. The "huge data" story is now de-risked from two sides.

## 9. Acknowledgments worth being honest about

Datashader is genuinely brilliant work. James Bednar and the HoloViz
team have been solving "visualize a billion points in Python" for almost
a decade. Anyone underestimating that work — or thinking we're going to
out-engineer it by switching to GPU — is going to be wrong.

Similarly, Dask is a serious system. We're not "more modern" than Dask
just because we've picked DuckDB for one workload class. Dask owns
problems we'll never touch.

Our position works precisely because we're solving a different problem:
**putting the web visualization ecosystem inside Qt apps with a desktop-
native UX.** That is a real, unmet need. It does not require us to be
better than Datashader at rasterization, or better than Dask at
distributed compute. It requires us to be better than no-one at a thing
no-one else is doing.

## 10. Recommended next steps

1. **Accept the integration framing.** Datashader and Dask are partners,
   not competitors. Update Moonshot C+D's plan to include Phase 3.5
   (Datashader backend) and `DaskSource` in Phase 1.
2. **Read the HoloViews + Panel API closely.** Their reactive Param model
   is well-thought-out; the planned `Signal`/`derived` layer should
   borrow ideas. Don't reinvent if `param` itself can be reused.
3. **Re-run the Phase 0 deck.gl spike.** Confirms our interactive ceiling.
4. **Add a Phase 0 Datashader spike (1 day).** Render a 1B-row scatter via
   Datashader to a PNG, deliver to a `WebBridgeView` via the binary
   transport spike. Confirms the end-to-end pipeline works before we
   commit to it.
5. **Sharpen the public messaging.** When we eventually announce the
   library/Studio, lead with "desktop-native interactive viz at scale,
   integrating the best of the Python ecosystem." Don't position as
   "Datashader replacement" or "the new Panel." That's a losing comparison.

## 11. Open question

The one decision this analysis raises:

> Does the Studio need to ship with Datashader as a hard dependency, or
> as an optional extra (`pip install qtwebstudio[datashader]`)?

Arguments for hard: it's *the* solution for the "too big for GPU" case;
without it, the "scales to any data" pitch has a gap.

Arguments for optional: Datashader pulls in Numba + LLVM (heavy install);
not every Studio user has billion-row data.

Recommend hard dependency. The Studio is a desktop app, install size is
not the main concern — the user installed Qt + Chromium already, an
extra 100 MB doesn't matter. The "any data, any time" story is too
valuable to compromise.
