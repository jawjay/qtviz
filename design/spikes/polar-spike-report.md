# [D119] Polar decision spike — Option B report (2026-08-06)

> **Recommendation: GO on Option B** — polar as a core transform +
> `PolarGrid` chrome. The spike rendered all three deliverables
> (`polar_demo`, `polar_bar`, radar) on **all three backends** using the
> **public API only** — zero `src/` changes (`polar_spike.py` in this
> directory is the whole proof; PNGs alongside). The decision to
> *implement* (the ~11 gallery examples) is the owner's call at review,
> per the gate in `design/archive/roadmap-post-rerun.md` §4.

## What the spike proved

- **The geometry is already expressible.** `(θ, r) → (x, y)` before the
  data seam + `aspect=1` + `grid=False` produces correct polar plots on
  pg/mpl/webengine with identical code. The 2.0 machinery did the heavy
  lifting: annotations lower everywhere (rings/spokes/labels needed zero
  backend edits), `Polygon(fill=True)` covers wedges and radar areas,
  callable accessors could carry the transform declaratively.
- **`AxisSpec(ticks=())` hides the rectilinear tick numbers** on every
  backend — the frame line remains, but the "this is secretly cartesian"
  tell is gone without any new surface vocabulary.
- **R1/events/state genuinely stay untouched** — the surfaces are
  rectilinear, so `ViewState`, brushes, `RangeEvent`s, backend switching
  all work today, unchanged, as predicted.

## What shipping it takes (estimate: M, nearly all core)

1. **`PolarGrid`** — a [D70]-class chrome element with one `lower()`
   (rings → outline marks, spokes → one pair-connected `Polyline`,
   labels → `TextMark`s). Options: `r_max` (or auto from the overlay's
   data), `rings`, `spokes`, `theta_labels` (degrees | custom | off),
   `r_labels`. The spike's 40-line prototype maps 1:1 onto marks.
2. **`qv.polar(element, theta=…, r=…)`** — sugar that rebinds the
   element's x/y channels through the transform (callable-accessor
   composition; serializable via `Expression` later if wanted).
   A `wedge(θ0, θ1, r0, r1)` point-builder helper covers polar bars.
3. **Gallery examples** — the ~11 polar entries + radar.
4. Freeze/CHANGELOG/api-docs triple for the two new names.

## Honest costs (unchanged from the §4 prediction, now confirmed)

- Hover/status readouts show x/y, not θ/r (denormalizing in the event
  layer is possible later; not in scope).
- No r-axis zoom semantics — zoom is rectangular. Fine for reading,
  wrong for polar-native interaction habits.
- The rectilinear axes *frame* still draws (ticks hideable today; a
  `frame=False` surface option would finish the look — S, optional).
- pg's PNG export pads the square aspect with dead space (pre-existing
  pg aspect/export artifact, not polar-specific).
- Radar legend entries from `Polygon(label=…)` show on pg/mpl; webengine
  drops shape legend entries (pre-existing annotation-legend delta —
  worth a line in the eventual docs).

## Why not Option A (native polar surfaces)

Nothing in the spike changed the §4 assessment: three divergent
implementations, a hand-built pg surface, and a new R1 coordinate
contract — XL and architectural — against a demand signal that still
doesn't exist. B delivers the gallery families for M with zero risk;
A remains available later if polar becomes a headline use-case.
