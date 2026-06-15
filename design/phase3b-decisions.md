# Phase 3b decisions — `hvplot` integration (D43) & `DynamicMap`/streams (D44)

> **Purpose.** A standalone briefing for the two open decisions that gate stage
> 3b of the HoloViews adapter. Written to be picked up cold in a future session:
> it explains each path, the real tradeoffs, the development effort, and where
> each one plugs into the code we already have. Companion to
> `milestone-holoviews-adapter.md` (the Phase 3 spec) and `discussion-items.md`
> entries **[D43]**/**[D44]**. Nothing here is decided yet — §"Decision checklist"
> at the end is what to fill in.

## 0. Where we are (so this reads cold)

- **Stage 3a is shipped** (commit `6f25c9c`): `qv.from_holoviews(obj)` translates a
  *static* HoloViews tree — containers + the 8 native elements + Points/Area — into
  native qtviz Nodes, with a webengine `RawFigure` fallback for the long tail. It is
  a pure function in `src/qtviz/adapter/holoviews.py`, public-API-only, holoviews
  imported lazily.
- **What 3a deliberately does NOT handle:** `DynamicMap` and stream-driven
  interactivity (→ **D44**), and the `hvplot` one-liner entry point (→ **D43**).
  Today `from_holoviews(a_dynamic_map)` raises `UnsupportedHoloViewsElement` —
  `DynamicMap` is not an `hv.core.Element`, so it falls through every branch. That
  raise is the exact seam where 3b plugs in.
- **Reactive substrate already exists** (Phase 4, [D38]): `qtviz.Signal` +
  `View(Signal[Node])` re-renders the View (debounced, GUI-thread, auto-disposed)
  whenever the signal changes — see `src/qtviz/core/view.py` `_is_reactive` /
  `_on_root_signal`. **D44's cheap path is mostly "wire a `DynamicMap` to a
  `Signal`," not "build reactivity."**
- **Dependency reality check:** `holoviews` is a dev dependency already; **`hvplot`
  is NOT installed**. This matters a lot for D43 below.

---

## 1. D43 — the `hvplot` integration mechanism

### 1.1 What "the win" actually is

`hvplot` gives pandas/xarray/dask users a fluent one-liner — `df.hvplot.scatter("x",
"y")` — that today returns a **HoloViews object** rendered in a browser via Bokeh.
The goal: let that same muscle memory produce a **native Qt widget** through qtviz.

The subtlety most people miss: **`df.hvplot.scatter(...)` returns a HoloViews object**
(an `Element`, `Overlay`, or — often — a `DynamicMap`). It is only *rendered* to
Bokeh when displayed. So "make hvplot use qtviz" can mean three quite different
things, with very different cost.

### 1.2 The three paths

#### Path A — hvplot-as-builder (translate what hvplot returns)

Let hvplot build the HoloViews object; feed it to the adapter we already have.

```python
import hvplot.pandas          # registers the .hvplot accessor
obj = df.hvplot.scatter("x", "y")     # → a HoloViews object, not rendered
view = qv.View(qv.from_holoviews(obj))  # ← reuses stage 3a verbatim
```

- **How it works:** zero new translation code — `from_holoviews` already handles the
  Element/Overlay/Layout that hvplot emits. The only new surface is a thin
  convenience wrapper (e.g. `qv.from_hvplot(df, kind="scatter", **kw)` or docs that
  say "just wrap it").
- **Coupling:** low. We depend only on hvplot's *output* (HoloViews objects), which
  is its stable public contract — the same public-API-only principle that kept 3a
  cheap ([D41]).
- **The catch:** hvplot frequently returns a **`DynamicMap`** (anything with
  `groupby=`, widgets, or `datashade=True`). Those need **D44** to render. For simple
  plots it returns a plain Element/Overlay and works today.
- **Dependency:** `hvplot` becomes an *optional* extra; not needed unless the user
  calls it.

#### Path B — a native `.qtviz` accessor (skip hvplot entirely)

Register our own pandas/xarray accessor that builds qtviz Elements directly.

```python
import qtviz.pandas          # registers df.qtviz
view = df.qtviz.scatter("x", "y", color_by="g")   # → qv.View, no HoloViews at all
```

- **How it works:** a `@pd.api.extensions.register_dataframe_accessor("qtviz")`
  class with one method per `kind` (`scatter`/`line`/`bar`/`hist`/`heatmap`/…) that
  maps straight onto our Element constructors. No HoloViews, no hvplot in the path.
- **Coupling:** none to HoloViews/hvplot. Full control over the API and error
  messages. Works offline trivially.
- **The catch:** we re-implement hvplot's `kind`→element surface and its keyword
  conventions ourselves. It's a *parallel* API to learn, not the one hvplot users
  already know — and hvplot's surface is broad (dozens of kinds + options), so
  "matching hvplot" is an open-ended commitment. Scope it to our 8 elements and say
  so.
- **Dependency:** none new (`pandas` already present).

#### Path C — register qtviz as a HoloViews/hvplot *plotting backend*

Make `df.hvplot.scatter(..., backend="qtviz")` and `hv.extension("qtviz")` work the
way `"bokeh"`/`"matplotlib"`/`"plotly"` do.

- **How it works:** HoloViews plotting backends are **not** a simple hook — a backend
  is a `Renderer` subclass plus a registry of `ElementPlot` classes (one per element
  per backend), wired into HoloViews' `Store`. This is essentially **"Option A —
  extend HoloViews"** from `native-pivot-research.md` §2c, which the project
  **explicitly rejected** as a maintenance sink (binds our roadmap to HoloViews'
  internal plot-class API, which drifts every release).
- **Coupling:** high and *internal*. This is the opposite of the public-API-only
  stance that has kept the adapter cheap.
- **Upside:** it's the most "native-feeling" for HoloViews power users — every hvplot
  option flows through, and `DynamicMap`/streams come for free because HoloViews
  drives them. But we'd be maintaining a plot-class hierarchy against a moving target.
- **Dependency:** `holoviews` (already), and deep knowledge of its plotting internals.

### 1.3 D43 comparison

| | A — hvplot-as-builder | B — `.qtviz` accessor | C — HoloViews backend |
|---|---|---|---|
| New translation code | ~none (reuses 3a) | one method per kind | plot-class per element |
| Coupling to hv/hvplot | low (public output) | none | **high (internals)** |
| Matches hvplot muscle memory | yes (it *is* hvplot) | no (parallel API) | yes (most native) |
| `DynamicMap`/widgets | inherits D44 | N/A (we don't emit them) | free (hv drives) |
| New dependency | hvplot (optional) | none | none |
| Offline-safe | yes (we render) | yes | yes |
| Rejected-before? | no | no | **yes — this is Option A** |
| Rough effort | **S (1–2 d)** | **M (3–6 d)** | **XL (weeks, ongoing)** |

### 1.4 Recommendation & what's still open

**Lead with Path A, optionally add B.** A is nearly free and gives real hvplot users
the exact call they know, deferring only the `DynamicMap` cases to D44. B is a nice
standalone ergonomic for users who don't want a HoloViews dependency, but it's a
second API to own — add it only if we want a hvplot-free entry point. **Avoid C** — it
re-opens the rejected Option A and trades our low-maintenance position for a moving
target.

Open questions to settle in the future session:
1. Do we want an hvplot-free entry point at all (i.e., is B worth owning), or is A
   enough?
2. If A: a real wrapper (`qv.from_hvplot(...)`) or just documentation?
3. Which `kind`s are in scope for B, if we build it? (Recommend: exactly our 8.)

---

## 2. D44 — `DynamicMap` / stream scope for 0.1

### 2.1 What `DynamicMap` + streams are

A `DynamicMap` is a *lazy, callback-driven* HoloViews object. It produces an element
on demand from two kinds of inputs (confirmed against hv 1.22):

- **`kdims`** — dimensions exposed as **widgets** (e.g. a `freq` slider). Resolving a
  value is public API: `dm[value]` / `dm.callback.callable(value)` → a concrete
  Element.
- **`streams`** — event objects (`RangeXY`, `BoundsXY`, `Tap`, `Selection1D`) whose
  `.event(**kwargs)` re-fires the callback. `stream.contents` gives the current
  payload; `stream.event(x_range=…, y_range=…)` pushes new state *into* HoloViews.

So interactivity has a **read** side (hv → us: "the map changed, re-render") and a
**write** side (us → hv: "the user brushed/zoomed, tell the stream"). The scope
decision is **how much of the write side we do for 0.1.**

### 2.2 What we already have to build on

- `View(Signal[Node])` re-renders on signal change — `core/view.py`. The read side is
  basically: subscribe to the `DynamicMap`, and on each new value
  `signal.set(from_holoviews(new_element))`.
- The typed event bus (`RangeEvent`/`SelectEvent`/`TapEvent`/`HoverEvent`) already
  fires from the native backends. The write side is: translate those into the
  matching `stream.event(...)` call.

### 2.3 The levels

#### Level 0 — render the *current* frame (stopgap)

Resolve the DynamicMap at its default kdim values once, translate, render statically.
No interactivity. Trivial (~0.5 d) but arguably worse than raising, because it
silently drops the interactivity the user asked for. Mention in docs only.

#### Level 1 — one-way re-render (read side)

The DynamicMap drives the View; qtviz does not push events back.

- **1a — kdim widgets:** render Qt controls (slider/combobox) for each kdim, and on
  change resolve `dm[values]` → `from_holoviews` → `signal.set(...)`. Reuses the
  reactive path; the new work is the **Qt widget panel + layout** and the
  kdim→widget mapping (continuous range → slider, discrete → combobox).
- **1b — param/stream-out without widgets:** if the user already drives the map from
  their own `Signal`/param, we just subscribe and re-render. Almost free given 1a's
  resolve plumbing.
- **Effort:** **M (4–7 d)**, most of it the kdim-widget UI, not the reactivity.
- **Fidelity:** covers the most common hvplot/HoloViews interactive case (a slider
  re-plots). Does **not** cover "brush in the plot updates the data" (that's the write
  side).

#### Level 2 — bidirectional stream sync (read + write)

Everything in Level 1, plus: qtviz typed events forward into HoloViews streams so
hv-side callbacks fire normally.

- **How:** a translation table `qtviz Event → hv stream.event(...)`:
  `RangeEvent → RangeXY(x_range, y_range)`, `SelectEvent → Selection1D(index)` /
  `BoundsXY`, `TapEvent → Tap(x, y)`. Subscribe to the View's event bus, debounce,
  and call `stream.event(**payload)`; the resulting new element flows back through the
  Level-1 read path.
- **The hard parts:** (1) **loop avoidance** — our event triggers a stream event,
  which produces a new render, which must not re-emit the originating event; needs an
  echo/guard + build-id discipline (we already use build-ids for stale renders).
  (2) **index/coordinate fidelity** — `Selection1D` is row indices into hv's data;
  mapping a native brush back to those indices must agree with how 3a built the frame.
  (3) **debounce/throttle** so a fast pan doesn't flood `stream.event`.
- **Effort:** **L (1.5–3 wk)** on top of Level 1, most of it correctness/edge cases
  and tests, not lines of code.
- **Fidelity:** full HoloViews interactivity — linked brushing, range-driven
  recompute, the works.

### 2.4 D44 comparison

| | L0 current-frame | L1 one-way | L2 bidirectional |
|---|---|---|---|
| Slider/widget re-plot | no | **yes** | yes |
| Brush/zoom → data update | no | no | **yes** |
| Reuses `Signal[Node]` | n/a | yes | yes |
| New UI work | none | kdim widget panel | + nothing beyond L1 UI |
| Hardest risk | (silently static) | widget mapping | loop-avoidance, index fidelity |
| Rough effort | 0.5 d | **M (4–7 d)** | **L (+1.5–3 wk)** |

### 2.5 Recommendation & what's still open

**Ship Level 1 for 0.1; defer Level 2.** Level 1 captures the dominant interactive
pattern (a widget re-plots) by leaning on reactivity we already built, and it's the
piece that unblocks **D43 Path A** for the many hvplot calls that return a
`DynamicMap`. Level 2's value is real but its cost is dominated by correctness work
(loop avoidance, index round-tripping) that's better done once the native event
semantics have settled and we have demand. Until Level 2 lands, a stream-only
DynamicMap (no kdims) should degrade to Level 0 + a clear warning, or the RawFigure
webengine fallback (full fidelity in a browser) — pick one in the session.

Open questions to settle:
1. Confirm Level 1 (one-way) is the 0.1 cut, Level 2 deferred.
2. For kdim widgets: do we render a built-in Qt control panel, or expose the kdims as
   `Signal`s and let the app build its own UI? (The second is cheaper and more
   composable; the first is more turnkey.)
3. Fallback for stream-only DynamicMaps before Level 2: warn-and-static, or route to
   webengine `RawFigure`?

---

## 3. How D43 and D44 interact

They are not independent. **D43 Path A's value is capped by D44**, because hvplot
emits `DynamicMap`s for any non-trivial call (`groupby`, widgets, `datashade`).
Concretely:

- D43 Path A + D44 Level 1 → hvplot one-liners with a `groupby`/widget work natively.
- D43 Path A + D44 Level 0 → only the *simplest* hvplot calls work; widget-bearing
  ones degrade or fall back.
- D43 Path B (`.qtviz` accessor) sidesteps this — we never emit a `DynamicMap`, so it
  works regardless of D44. That's a point in B's favor *if* we don't do D44 Level 1.

So a coherent 0.1 story is one of:
- **Cheapest coherent:** D43 **B** (accessor) + D44 **L1** (widgets via Signals). No
  hvplot dependency, interactive, fully ours.
- **Most hvplot-native:** D43 **A** (translate hvplot output) + D44 **L1**. Requires
  the optional hvplot dep; gives real hvplot users their exact call.
- **Do both A and B** + L1 — widest reach, more API surface to own.

## 4. Effort summary (rough, full-time engineer-days)

| Item | Path/Level | Effort |
|---|---|---|
| D43 hvplot entry | A — translate output | S · 1–2 d |
| D43 hvplot entry | B — `.qtviz` accessor | M · 3–6 d |
| D43 hvplot entry | C — hv plotting backend | XL · weeks + ongoing (rejected) |
| D44 DynamicMap | L1 — one-way re-render | M · 4–7 d |
| D44 DynamicMap | L2 — bidirectional | L · +1.5–3 wk |

> Estimates are order-of-magnitude, dominated by tests/edge-cases not LOC; calibrate
> against the actual session. The reactive substrate and 3a translation already exist,
> which is why L1 and Path A are small.

## 5. Decision checklist (fill in next session)

- [ ] **D43:** Path A only · A+B · B only · (C is rejected). _Decision:_ ____
- [ ] If A: wrapper `qv.from_hvplot(...)` or docs-only? _Decision:_ ____
- [ ] If B: which `kind`s (recommend our 8)? _Decision:_ ____
- [ ] **D44:** confirm L1 for 0.1, L2 deferred. _Decision:_ ____
- [ ] **D44:** kdim widgets as built-in Qt panel, or exposed as `Signal`s for the app? _Decision:_ ____
- [ ] **D44:** stream-only DynamicMap fallback before L2 — warn-and-static or webengine RawFigure? _Decision:_ ____
- [ ] Update [D43]/[D44] status in `discussion-items.md` once chosen.
