# Stability & deprecation policy (2.0)

As of 2.0, qtviz renews the 1.0 promise: **the surface you hold in your head
stays put.** 2.0 was the one planned clean break (the Mark IR + uniform
surface, [D121]–[D136], amended pre-publication by [D140]) — 71 names, one
channel vocabulary, one norm spec,
`.opts()`/`show()` — and the freeze now pins that surface
(`FROZEN_2_0`). This page defines exactly what the promise covers and how it
can change.

## What is public

- **Every name in `qtviz.__all__`** — the elements, composition (`Overlay` /
  `Layout` / `View` / `show`), data binding (`col` / `lit` / `tabular` /
  `gridded` / `stream`), styling (`Theme` / `Norm` / `OverlayOptions` /
  `AxisSpec` …), events, reactive primitives, and the adapter entry points.
  The suite pins this list exactly (`test_api_freeze.py`) — it cannot drift
  silently. (Typing aliases and internal machinery left the contract in 2.0:
  `Accessor`, `Expression`, `ColorSpec`, `StreamRef`, `DMapBinding`,
  `negotiate`, `auto_negotiate` remain importable from their submodules but
  are no longer frozen names.)
- **The extension contracts**: the `Backend` protocol (2.0 adds
  `honored_options()`, `requires_display`, and mark drawers), the
  `qtviz.backends` entry-point group ([D125] — a third-party backend
  registers with zero qtviz edits), the `DataRef` /
  `TabularRef` / `GriddedRef` contract (including `materialize(max_cells=)`,
  `window()`, `subscribe()` + `version()` for live refs), and the typed event
  dataclasses. Third-party backends and data adapters build on these; see
  [Writing a backend](backends.md).
- **Documented behavior contracts**: honor-or-warn (§3.4 — a recommended
  option is honored or warns, never silently dropped; since 2.0 declared
  once per element as `HONORED_NATIVE`/`HONORED_BY_LOWERING` and proven by
  the [D123] perturbation guard), capability honesty (a declared capability
  has a code path), R1 (every coordinate crossing the seam is data space),
  and legend honesty ([D48]).

## What is NOT public

- Underscore modules and attributes (`qtviz.core._scales`, `_renderers`,
  `_qtviz_legend`, …) — internal, changeable at any time.
- **The objects returned by `handle.native()` / `View.native()`** — the escape
  valve is stable as an *entry point*; what it returns is backend-native and
  non-portable **by design** ([D53]).
- Backend-internal layouts (Plotly figure-dict shapes, pyqtgraph item
  composition, the webengine bridge protocol).
- The `design/` corpus — decisions, not API.

## Versioning

qtviz follows [semver](https://semver.org):

- **Patch** (2.0.x): fixes only, no surface or behavior-contract changes.
- **Minor** (2.x.0): additive surface (new elements, options, methods) and
  completed deprecations. Additions update the freeze list + CHANGELOG in the
  same change.
- **Major**: anything that breaks the public surface without a deprecation
  path.

## Deprecation path

1. The name keeps working and emits a `DeprecationWarning` naming its
   replacement.
2. It stays for **at least two minor releases** after the warning first ships.
3. Removal lands in a minor release, called out in the CHANGELOG.

Non-fatal *behavioral* degradation (an option a backend can't honor) is a
`QtvizWarning` — filterable, and never silent.

### Current ledger

| Name | Warned since | Removal |
|---|---|---|
| *(empty — the 2.0 break cleared the ledger)* | | |

The 1.x ledger for the record: `qtviz.Options` (warned 0.2.0, removed 1.1)
and the `qtwebplot` import shim (warned 0.1.0, removed 1.0). The 1.x→2.0
renames themselves shipped **without** deprecation shims — a deliberate
one-time exception for a private repo with no external users; the full
rename table is in the 2.0.0 CHANGELOG entry.

## Release mechanics

Private repo, by owner decision — release = version bump + dated CHANGELOG +
git tag; no PyPI, no Pages. The release gates (suite, ruff, mypy, coverage,
strict docs build) are local commands recorded in `RELEASING.md`.
