# Stability & deprecation policy (1.0)

As of 1.0, qtviz makes a promise: **the surface you hold in your head stays
put.** This page defines exactly what that promise covers and how it can
change.

## What is public

- **Every name in `qtviz.__all__`** — the elements, composition (`Overlay` /
  `Layout` / `View`), data binding (`col` / `Expression` / `tabular` /
  `gridded` / `stream`), styling (`Theme` / `OverlayOptions` / `AxisSpec` …),
  events, reactive primitives, and the adapter entry points. The suite pins
  this list exactly (`test_api_freeze.py`) — it cannot drift silently.
- **The extension contracts**: the `Backend` protocol +
  `register_backend`-style registry, the `DataRef` /
  `TabularRef` / `GriddedRef` contract (including `materialize(max_cells=)`,
  `window()`, `subscribe()` + `version()` for live refs), and the typed event
  dataclasses. Third-party backends and data adapters build on these; see
  [Writing a backend](backends.md).
- **Documented behavior contracts**: honor-or-warn (§3.4 — a recommended
  option is honored or warns, never silently dropped), capability honesty
  (a declared capability has a code path), R1 (every coordinate crossing the
  seam is data space), and legend honesty ([D48]).

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

- **Patch** (1.0.x): fixes only, no surface or behavior-contract changes.
- **Minor** (1.x.0): additive surface (new elements, options, methods) and
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
| `qtviz.Options` | 0.2.0 | **1.1** (0.2 promised "importable through 1.0" — kept to the letter) |
| `qtwebplot` import shim | 0.1.0 | **removed in 1.0** (promised two releases; five elapsed) |

## Release mechanics

Private repo, by owner decision — release = version bump + dated CHANGELOG +
git tag; no PyPI, no Pages. The release gates (suite, ruff, mypy, coverage,
strict docs build) are local commands recorded in `RELEASING.md`.
