# Milestone — 0.6 "Live & linked" ([D63] — the differentiator)

> The improvement-plan flagship: *the reason to choose native Qt over a
> notebook*. Low-latency streaming + linked brushing through a datashaded view,
> as plain desktop widgets. Decisions **[D76]–[D78]**; resolves the
> long-open **[D7]** (update coalescing) and applies [D52] capability honesty
> to ourselves: pyqtgraph has declared `streaming=True` since 0.1 with no
> incremental code path behind it — rebuild was the only way. 0.6 backs it.

## 0. Goal & scope

**Goal.** A live telemetry dashboard — a streaming feed appending at wire rate,
a rolling window, a datashaded history panel, and a brush on the raster
filtering a linked panel — at interactive frame rates, in ≤100 example LOC.

**In scope.**
- **[D76] A streaming data source:** `qv.stream(...)` → a mutable, append-able
  tabular `DataRef` with ring-buffer rolling windows, notifying through the
  *existing* (designed-but-dead) `DataRef.subscribe` seam.
- **[D77] Incremental refresh (resolves [D7]):** `RenderHandle.
  set_element_data` — pyqtgraph updates live items in place (`setData`), no
  rebuild; appends coalesce to one refresh per tick; other backends fall back
  honestly (mpl: debounced rebuild, `streaming=False` as declared; webengine:
  `update()` → Plotly `react`, which diffs).
- **[D78] Raster selection:** brushing a datashaded view emits a `SelectEvent`
  for the *source* element — row indices when the source is eager, and always
  the data-space `bounds` (the predicate that scales: a lazy source filters
  downstream via `window(bounds)`, no row identity needed).

**Non-goals.** Bidirectional streams / write-back (HoloViews L2 stays parked);
WebSocket/ZMQ plumbing (bring your own thread; `append` is thread-safe);
per-point partial *diffing* (in-place `setData` of the current window is the
honest, robust cut); webengine per-trace extend (its `react` diff is its
streaming story, documented); animation API (still a non-goal, [D58]).

---

## 1. The streaming source ([D76])

```python
feed = qv.stream({"t": float, "v": float}, window=100_000)   # ring buffer
feed.append(t=timestamps, v=values)          # any thread; arrays or scalars
view = qv.View(qv.Curve(feed, x="t", y="v"))  # live — no other wiring
```

- `StreamRef(TabularRef)`: named columns with dtypes, a `window=` max-row ring
  buffer (old rows drop on append — lifting the spec §12 "stream-time
  auto-rolling" deferral), `append(**columns)` under a lock (any thread),
  `subscribe(cb)` — the base-contract method every other ref stubs as NOOP —
  firing after each append. `version()` counts appends; `fingerprint` =
  (id, version) so value identity stays coherent.
- Purity intact (R1/[D38]): the *Element* stays immutable — it holds a handle
  to changing data, exactly like a pandas frame the user mutates. The only new
  power is that this handle *tells* subscribers. No signals on Elements.
- Buffer: per-column growable numpy arrays with amortized doubling + ring
  wraparound; `resolve_channels` snapshots contiguous views (copy) so a render
  never sees a torn append.

## 2. Incremental refresh ([D77] — resolves [D7])

- **`RenderHandle.set_element_data(element_id, arrays) -> bool`** — write new
  role-keyed arrays into the live item; `False` = unsupported (caller falls
  back). pyqtgraph implements it for `ScatterPlotItem`/`PlotCurveItem`
  (`setData` — milliseconds at 100k points) and refreshes the ViewBox
  selectable registry so brushing stays truthful; anything else returns False.
- **`StreamBinding`** (View-owned QObject): at build, walk the *original*
  (unresolved) root — the resolved tree holds snapshots — and subscribe once
  per distinct subscribable ref. Appends arrive on any thread → a queued Qt
  signal marshals to the GUI thread → **coalesced to one refresh per tick**
  (single-shot 0 ms timer, the [D40] pattern; this is [D7]'s answer). Each
  refresh re-resolves the streamed elements' channels and tries
  `set_element_data`; any False → one debounced `handle.update(resolved
  root)` (mpl rebuild / webengine react) instead.
- Ranges: pyqtgraph auto-ranges while the user hasn't zoomed (native ViewBox
  behavior); a user zoom is never fought (no forced autorange on refresh).
- Capability honesty: pyqtgraph `streaming=True` finally backed by code;
  matplotlib stays `False` (its fallback is the debounced rebuild); webengine
  keeps `True` via the `react` diff — documented as such.

## 3. Raster selection ([D78])

Brushing a datashaded view today emits **nothing** (the raster Image never
registers as selectable). 0.6 wires it with scale-honest semantics:

- At attach, an `Image` carrying `_raster_source` registers a selectable for
  the **source element's id**:
  - **eager source** — the already-resolved x/y arrays; a brush masks them and
    emits `SelectEvent(source_id, indices, bounds)` (identical to a native
    Scatter brush; ~tens of ms at 10M rows, inside the Select throttle);
  - **lazy source** — a *bounds-only* selectable: `SelectEvent(source_id, [],
    bounds)`. Row identity would force a compute; the bounds ARE the
    selection — downstream filters by `ref.window(x=…, y=…)` predicate
    pushdown, which is how big-data crossfilter should work anyway.
- Both native backends (`_events.attach` + the mpl selectables list). The
  regrid `_grid_source` Images are *grids* (no row identity) — out of scope,
  unchanged.
- Closes the [D58] "pixel→source rows" deferral for the eager case and gives
  the lazy case its honest predicate form.

## 4. Discussion items (recommended; confirm at review)

### [D76] Stream as a DataRef through the subscribe seam
*Alternatives:* `Element(data=Signal)` (rejected long ago, [D38] — breaks
purity); a Qt-signal-based source (rejected: the data layer stays Qt-free;
marshaling belongs to the View-side binding).

### [D77] In-place window refresh, one per tick — not per-point diffing
`setData` of the current window is O(window) per frame and unconditionally
correct; per-point extend paths are error-prone across wraparound/window-drop.
*Alternative:* `extendTraces`-style appends (revisit if profiling ever shows
the window write as the bottleneck — the seam allows it).

### [D78] Indices-when-eager, bounds-always
*Alternatives:* compute indices for lazy sources (rejected: forces a full
scan on every brush — the exact cost datashader exists to avoid); no raster
selection (status quo — rejected, it's the crossfilter gap).

## 5. Test plan (TDD — write first)

**Tier-1:** StreamRef append/ring-window/dtype/thread-lock semantics; version
+ fingerprint churn; subscribe fires; resolve_channels snapshot isolation
(mutating after resolve doesn't change the snapshot); schema/size.

**Tier-2 (offscreen):** a Curve/Scatter on a stream updates **in place**
(same item identity, new data, no rebuild) after `append` + event-loop tick;
N rapid appends → exactly one refresh (coalescing, [D7]); rolling window
drops old points in the rendered item; brush selectables stay truthful after
appends; mpl fallback rebuilds (item identity *changes*, data correct);
zoomed ViewBox is not re-ranged by a refresh. Raster selection: brush a
datashaded (eager) view → SelectEvent with correct indices + bounds on both
native backends; lazy (dask) source → empty indices, correct bounds;
crossfilter: raster brush drives a linked panel via signals.

## 6. Benchmarks (per cadence)
`test_bench_stream.py`: `append` cost (µs-scale, it's on the producer's
thread); end-to-end append→painted-frame refresh at a 100k-point window
(ms-scale — the interactive-rate claim); `set_element_data` at 100k
(setData cost).

## 7. Phased increments (review at each boundary)
1. **StreamRef + `qv.stream`** ([D76]) — the pure source, fully tier-1.
2. **Incremental refresh** ([D77]) — `set_element_data` (pyqtgraph) +
   `StreamBinding` (subscribe/marshal/coalesce/fallback) + honesty tests.
3. **Raster selection** ([D78]) — both native backends + crossfilter test.
4. **Acceptance**: `examples/34_streaming_telemetry.py` (§0 dashboard,
   ≤100 LOC) + benchmarks + CHANGELOG.

## 8. Risks
| # | Risk | Mitigation |
|---|---|---|
| 1 | Cross-thread appends race the GUI read | lock in StreamRef; resolve snapshots copy under the lock; marshaling via queued signal |
| 2 | Refresh loop fights user zoom | never call autorange; test pins a zoomed range across refreshes |
| 3 | Rebuild-fallback storms on mpl at high append rates | the per-tick coalescer bounds it at one rebuild per event-loop turn; debounce documented |
| 4 | 10M-row eager mask per brush too slow | inside the 50 ms Select throttle; benchmarked; lazy path never masks |
| 5 | Streamed element also datashaded (`scale="auto"` routes) | out of scope: stream + datashader routes to rebuild fallback (warn-free, documented); revisit with demand |

## 9. Acceptance
`examples/34_streaming_telemetry.py` (≤100 LOC): a worker thread appends
simulated telemetry at wire rate into `qv.stream(window=…)`; a live Curve
panel updates in place at interactive rates with a rolling window; a second,
datashaded panel of the accumulated history re-aggregates on zoom; brushing
the raster emits a SelectEvent whose bounds filter a third linked panel
(signals). pyqtgraph `streaming=True` is backed by `set_element_data`; the
suite pins in-place identity, coalescing, window-drop, zoom-respect, and
raster-brush indices/bounds. Suite green; ruff clean; benchmarks within
ceilings.
